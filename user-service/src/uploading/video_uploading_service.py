from flask import Flask, request, jsonify, Blueprint
from database import User, Video, db
from botocore.exceptions import NoCredentialsError
import boto3,time
from redis import Redis


video_uploading_service = Blueprint("video_uploading_service", __name__)

SECRET_KEY = 'your_secret_key'

AWS_ACCESS_KEY_ID = 'AKIASQQQG2XF4V573GL6'  
AWS_SECRET_ACCESS_KEY = 'CdttLTHaOvXicRjrrkBXrqpK2daZNWXeG7fh3uUu'  
AWS_BUCKET_NAME = 'flasks3scalable' 

s3_client = boto3.client('s3', aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY)

r = Redis(host='localhost', port=6379, decode_responses=True)

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
            user = User.query.filter_by(username=username).first()
            new_video = Video(title=video_title, 
                            description=video_description,
                            user_id=user.id,
                            s3_filename=video_name)
            db.session.add(new_video)
            db.session.commit()
            r.publish('video_upload', 'New video uploaded and ready for processing')
            return jsonify({'message': 'Video uploaded successfully'}), 200
        except NoCredentialsError:
            return jsonify({'error': 'AWS credentials not available'}), 403
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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