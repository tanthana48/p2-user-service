from flask import Flask, request, jsonify, Blueprint
from database import User, Video, Like, Comment, Notification, db
from botocore.exceptions import NoCredentialsError
import boto3
from redis import Redis
import os
import m3u8

video_uploading_service = Blueprint("video_uploading_service", __name__)

SECRET_KEY = 'your_secret_key'

AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
AWS_BUCKET_NAME = os.environ.get('AWS_BUCKET_NAME')

s3_client = boto3.client('s3', aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY)
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))

r = Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
pubsub = r.pubsub()

@video_uploading_service.route('/api/get-presigned-m3u8', methods=['POST'])
def get_presigned_m3u8():
    data = request.json
    hls_filename = data['hls_filename']

    m3u8_obj = s3_client.get_object(Bucket=AWS_BUCKET_NAME, Key=hls_filename)
    m3u8_content = m3u8_obj['Body'].read().decode('utf-8')

    playlist = m3u8.loads(m3u8_content)

    # Replace each .ts segment URL with a presigned URL
    for segment in playlist.segments:
        segment.uri = generate_presigned_url_get(segment.uri)

    # Return the modified m3u8 content
    return jsonify({'m3u8_content': playlist.dumps()}), 200

@video_uploading_service.route('/api/get-presigned-url-thumbnail', methods=['POST'])
def get_presigned_url_thumbnail():
    data = request.json
    thumbnail_filename = data['thumbnail_filename']

    presigned_url = generate_presigned_url_get(thumbnail_filename)
    print(presigned_url)
    return jsonify({'presigned_url': presigned_url}), 200


@video_uploading_service.route('/api/get-presigned-url', methods=['POST'])
def get_presigned_url():
    data = request.json
    file_name = data['fileName']
    file_type = data['fileType']

    presigned_url = generate_presigned_url(file_name, file_type)
    return jsonify({'presigned_url': presigned_url}), 200


@video_uploading_service.route('/api/confirm-upload', methods=['POST'])
def confirm_upload():
    try:
        data = request.json
        video_name = data['s3_filename']
        video_title = data['title']
        video_description = data['description']
        username = data['username']
        try:
            base_name = os.path.splitext(video_name)[0]
            hls_filename = base_name + '_converted.m3u8'
            s3_filename = base_name + '_converted.mp4'
            thumbnail_filename = base_name + '_converted.jpg'
            r.rpush('video_name', video_name)
            user = User.query.filter_by(username=username).first()
            new_video = Video(title=video_title, 
                            description=video_description,
                            user_id=user.id,
                            s3_filename=s3_filename,
                            hls_filename = hls_filename,
                            thumbnail_filename= thumbnail_filename,
                            status='uploading')
            db.session.add(new_video)
            db.session.commit()
            print(f"Published video name: {video_name}")
            return jsonify({'message': 'Video uploaded successfully'}), 200
        except NoCredentialsError:
            return jsonify({'error': 'AWS credentials not available'}), 403
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def generate_presigned_url_get(filename):
    presigned_url = s3_client.generate_presigned_url(
        'get_object',
        Params={
            'Bucket': AWS_BUCKET_NAME,
            'Key': filename
        },
        ExpiresIn=3600
    )
    return presigned_url

def generate_presigned_url(filename, file_type):
    presigned_url = s3_client.generate_presigned_url(
        'put_object',
        Params={
            'Bucket': AWS_BUCKET_NAME,
            'Key': filename,
            'ContentType': file_type
        },
        ExpiresIn=3600
    )
    return presigned_url

@video_uploading_service.route('/api/increment-views', methods=['POST'])
def increment_views():
    video_id = request.json['video_id']
    video = Video.query.get(video_id)
    
    if video:
        video.views += 1
        db.session.commit()
        return jsonify(success=True, views=video.views)
    else:
        return jsonify(error="Video not found", video_id=video_id), 404

@video_uploading_service.route('/api/videos', methods=['GET'])
def get_videos():
    try:
        videos = Video.query.all()
        if not videos:
            return jsonify({'message': 'No videos found'}), 404

        video_list = []
        for video in videos:
            video_data = {
                'id': video.id,
                'title': video.title,
                'description': video.description,
                'date': video.date,
                'views': video.views,
                'user_id': video.user_id,
                's3_filename': video.s3_filename,
                'hls_filename': video.hls_filename,
                'status': video.status
            }
            if video.status == 'success':
                video_list.append(video_data)

        return jsonify({'videos': video_list}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@video_uploading_service.route('/api/myvideos', methods=['POST'])
def get_myvideos():
    try:
        data = request.json
        username = data['username']
        user = User.query.filter_by(username=username).first()
        user_id = user.id
        videos = Video.query.filter_by(user_id=user_id).first()
        if not videos:
            return jsonify({'message': 'No videos found'}), 404

        video_list = []
        for video in videos:
            video_data = {
                'id': video.id,
                'title': video.title,
                'description': video.description,
                'date': video.date,
                'views': video.views,
                'user_id': video.user_id,
                's3_filename': video.s3_filename,
                'hls_filename': video.hls_filename,
                'status': video.status
            }
            video_list.append(video_data)

        return jsonify({'videos': video_list}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    

# @socketio.on('like-video')
@video_uploading_service.route('/api/increment-likes', methods=['POST'])
def handle_like_video():
    user_id = request.json['user_id']
    user_id = User.query.get(user_id)
    video_id = request.json['video_id']
    video_id = Video.query.get(video_id)
    if user_id:
        existing_like = Like.query.filter_by(user_id=user_id, video_id=video_id).first()
        if not existing_like:
            new_like = Like(user_id=user_id, video_id=video_id)
            db.session.add(new_like)
            db.session.commit()

            new_like_count = Like.query.filter_by(video_id=video_id).count()
            # emit('update-like-count', {'video_id': video_id, 'like_count': new_like_count}, broadcast=True)

# @socketio.on('unlike-video')
@video_uploading_service.route('/api/descrement-likes', methods=['POST'])
def handle_unlike_video():
    user_id = request.json['user_id']
    user_id = User.query.get(user_id)
    video_id = request.json['video_id']
    video_id = Video.query.get(video_id) 
    if user_id:
        existing_like = Like.query.filter_by(user_id=user_id, video_id=video_id).first()
        if existing_like:
            db.session.delete(existing_like)
            db.session.commit()

            new_like_count = Like.query.filter_by(video_id=video_id).count()
            # emit('update-like-count', {'video_id': video_id, 'like_count': new_like_count}, broadcast=True)


def get_like_count_for_video(video_id):
    return Like.query.filter_by(video_id=video_id).count()

# @socketio.on('post-comment')
@video_uploading_service.route('/api/post-comment', methods=['POST'])
def handle_post_comment():
    user_id = request.json['user_id']
    user_id = User.query.get(user_id)
    video_id = request.json['video_id']
    video_id = Video.query.get(video_id) 
    text = request.json['text']
    
    if not text.strip():
        return jsonify({'message': 'No text'}), 404

    if user_id and video_id:
        new_comment = Comment(user_id=user_id, video_id=video_id, text=text)
        db.session.add(new_comment)
        db.session.commit()

        # emit('new-comment', {
        #     'user_id': user_id,
        #     'video_id': video_id,
        #     'text': text,
        #     'timestamp': new_comment.created_at.isoformat()
        # }, room=video_id)
        notify_users(video_id,text)

@video_uploading_service.route('/api/notifications', methods=['GET'])
def get_notifications():
    user_id = request.json['user_id']
    user_id = User.query.get(user_id)
    notifications = Notification.query.filter_by(user_id=user_id, read=False).all()
    return jsonify([notification.to_dict() for notification in notifications])

@video_uploading_service.route('/api/notifications/<int:notification_id>/read', methods=['POST'])
def mark_notification_as_read():
    user_id = request.json['user_id']
    user_id = User.query.get(user_id)
    notification_id = request.json['notification_id']
    notification_id = Notification.query.get(notification_id)
    if notification_id and notification_id.user_id == user_id:
        notification_id.read = True
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'error': 'Invalid notification ID or user ID'}), 400

def notify_users(video_id, comment_text):

    users_liked = User.query.join(Like).filter(Like.video_id == video_id).all()
    users_commented = User.query.join(Comment).filter(Comment.video_id == video_id).all()
    users_to_notify = list(set(users_liked + users_commented))

    message = f"New activity on a video you're following: {comment_text}"

    for user in users_to_notify:
        notification = Notification(user_id=user.id, message=message)
        db.session.add(notification)
        
        # emit('new-notification', {'message': message}, room=str(user.id))
    db.session.commit()

@video_uploading_service.route('/api/worker-status', methods=['POST'])
def update_thumbnail():
    data = request.json
    video_name = data["file_name"]
    status = data["status"]

    video = Video.query.filter_by(s3_filename=video_name).first()
    if video:
        video.status = status
        db.session.commit()
        return jsonify({'message': 'Workers updated successfully'}), 200
    else:
        return jsonify({'error': 'Video not found'}), 404
