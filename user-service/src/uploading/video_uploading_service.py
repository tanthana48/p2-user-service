from flask import Flask, request, jsonify, Blueprint, current_app
from database import User, Video, Like, Comment, db
from botocore.exceptions import NoCredentialsError
import boto3
from redis import Redis
import json
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
    if not thumbnail_filename:
        return jsonify({'error': 'thumbnail_filename is required'}), 400

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
                            status='processing')
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
                'thumbnail_filename': video.thumbnail_filename,
                'status': video.status
            }
            if video.status == 'success':
                video_list.append(video_data)

        return jsonify({'videos': video_list}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@video_uploading_service.route('/api/myvideos/<username>', methods=['GET'])
def get_myvideos(username):
    try:
        user = User.query.filter_by(username=username).first()
        if not user:
            return jsonify({'message': 'User not found'}), 404
        user_id = user.id
        videos = Video.query.filter_by(user_id=user_id).all()  # Use .all() here
        if not videos:
            return jsonify({'message': 'No videos found'}), 404

        video_list = [ {
                'id': video.id,
                'title': video.title,
                'description': video.description,
                'date': video.date,
                'views': video.views,
                'likes': video.likes,
                'user_id': video.user_id,
                's3_filename': video.s3_filename,
                'hls_filename': video.hls_filename,
                'thumbnail_filename': video.thumbnail_filename,
                'status': video.status
            } for video in videos ]

        return jsonify({'videos': video_list}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

def delete_video_by_id(video_id):
    try:
        video = Video.query.get(video_id)
        if video is None:
            return False
        
        db.session.delete(video)
        db.session.commit()
        return True
    except Exception:
        db.session.rollback()
        return False

@video_uploading_service.route('/api/delete-video/<int:video_id>', methods=['DELETE'])
def delete_video(video_id):
    try:
        success = delete_video_by_id(video_id)
        if success:
            return jsonify({'message': 'Video successfully deleted'}), 200
        else:
            return jsonify({'error': 'Could not delete video'}), 400
    except Exception as e:
        return jsonify({'error': 'Internal server error'}), 500
    
@video_uploading_service.route('/api/check-like/<int:video_id>/<username>', methods=['GET'])
def check_user_like(video_id,username):
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    like = Like.query.filter_by(user_id=user.id, video_id=video_id).first()
    return jsonify({'isLiked': like is not None})

@video_uploading_service.route('/api/increment-likes/<username>', methods=['POST'])
def handle_like_video(username):
    video_id = request.json['video_id']
    video_id = Video.query.get(video_id)
    user_id = User.query.filter_by(username=username).first()
    if (video_id):
        video_id.likes += 1
        new_like = Like(user_id=user_id.id, video_id=video_id)
        db.session.add(new_like)
        db.session.commit()
        return jsonify(success=True, likes=video_id.likes)
    else:
        return jsonify(error="Video not found", video_id=video_id), 404

@video_uploading_service.route('/api/descrement-likes/<username>', methods=['POST'])
def handle_unlike_video(username):
    video_id = request.json['video_id']
    video_id = Video.query.get(video_id) 
    user_id = User.query.filter_by(username=username).first()
    if video_id:
        video_id.likes-=1
        existing_like = Like.query.filter_by(user_id=user_id.id, video_id=video_id).first()
        db.session.delete(existing_like)
        db.session.commit()
        return jsonify(success=True, likes=video_id.likes)
    else:
        return jsonify(error="Video not found", video_id=video_id), 404

@video_uploading_service.route('/api/post-comment/<username>', methods=['POST'])
def handle_post_comment(username):
    video_id = request.json['video_id']
    video_id = Video.query.get(video_id) 
    text = request.json['text']
    user_id = User.query.filter_by(username=username).first()
    if not text.strip():
        return jsonify({'message': 'No text'}), 404

    if user_id and video_id:
        new_comment = Comment(user_id=user_id.id, video_id=video_id, text=text)
        db.session.add(new_comment)
        db.session.commit()

        notify_users(video_id,text)

@video_uploading_service.route('/api/comments/<int:video_id>', methods=['GET'])
def get_comments(video_id):
    comments = Comment.query.filter_by(video_id=video_id).all()
    return jsonify([comment.to_dict() for comment in comments])

def notify_users(video_id, comment_text):

    users_liked = User.query.join(Like).filter(Like.video_id == video_id).all()
    users_commented = User.query.join(Comment).filter(Comment.video_id == video_id).all()
    users_to_notify = list(set(users_liked + users_commented))
    message = f"New activity on a video you're following: {comment_text}"

    notifications = [
        {
            'user_id': user.id,
            'message': message,
            'video_id': video_id
        }
        for user in users_to_notify
    ]

    notifications_json = json.dumps(notifications)

    r.rpush('notifications', notifications_json)

@video_uploading_service.route('/api/worker-status', methods=['POST'])
def update_thumbnail():
    data = request.json
    video_name = data["video_filename"]
    status = data["status"]

    video = Video.query.filter_by(s3_filename=video_name).first()
    if video:
        video.status = status
        db.session.commit()
        return jsonify({'message': 'Workers updated successfully'}), 200
    else:
        return jsonify({'error': 'Video not found'}), 404

