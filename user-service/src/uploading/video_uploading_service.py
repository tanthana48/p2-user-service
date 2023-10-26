from flask import Flask, request, jsonify, Blueprint
from database import User, Video, db
from botocore.exceptions import NoCredentialsError
import boto3,time

video_uploading_service = Blueprint("video_uploading_service", __name__)

SECRET_KEY = 'your_secret_key'

AWS_ACCESS_KEY_ID = 'AKIASQQQG2XF4KSBPOMG'  
AWS_SECRET_ACCESS_KEY = 'd78LendV+ExAfroowAQkIL3tN+YyNviJOANolBz4'  
AWS_BUCKET_NAME = 'flasks3scalable' 

s3_client = boto3.client('s3', aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY)

@video_uploading_service.route('/api/upload', methods=['POST'])
def upload_video():
    try:
        video_file = request.files['video']
        video_title = request.form['title']
        video_description = request.form['description']
        if video_file:
            if not is_video_too_long(video_file):
                username = request.form['username']
                user = User.query.filter_by(username=username).first()
                if user:
                    file_name = f"{username}_{int(time.time())}.mp4"
                    try:
                        s3_client.upload_fileobj(video_file, AWS_BUCKET_NAME, file_name)
                        new_video = Video(
                            title=video_title,
                            description=video_description,
                            user_id=user.id,
                            s3_filename=file_name
                        )
                        db.session.add(new_video)
                        db.session.commit()
                        presigned_url = generate_presigned_url(video_file.filename)
                        return jsonify({'presigned_url': presigned_url}), 200
                    except NoCredentialsError:
                        return jsonify({'error': 'AWS credentials not available'}), 403
                else:
                    return jsonify({'error': 'User not found'}), 404
            else:
                return jsonify({'error': 'Video is too long (max: 1 minute)'}), 400
        else:
            return jsonify({'error': 'Video file missing'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def is_video_too_long(video_file):
    max_duration = 60 
    if video_file.content_length > max_duration: return True 
    return False

def generate_presigned_url(filename):
    presigned_url = s3_client.generate_presigned_url(
        'put_object',
        Params={'Bucket': AWS_BUCKET_NAME, 'Key': filename},
        ExpiresIn=3600  
    )
    return presigned_url

@video_uploading_service.route('/api/videos', methods=['GET'])
def get_videos():
    try:
        videos = Video.query.all()
        if not videos:
            return jsonify({'message': 'No videos found'}), 404

        video_list = [{
            'id': video.id,
            'title': video.title,
            'description': video.description,
            'date': video.date,
            'views': video.views,
            'user_id': video.user_id,
            's3_filename': video.s3_filename,
            'hls_filename': video.hls_filename,
            'thumbnail_filename': video.thumbnail_filename
        } for video in videos]

        return jsonify({'videos': video_list}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500