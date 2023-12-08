# Toktik

A video streaming platform




## Authors

- Thana Lertlum-umpaiwong 6380271

- Kloena Burazeri


## All service repos
    1. https://github.com/tanthana48/p2-user-service
    2. https://github.com/tanthana48/p2-frontend
    3. https://github.com/kloe-b/p2-video-processing-service
    4. https://github.com/tanthana48/p2-notification-service

    - the first one is the backend
    - the second one is the frontend
    - the third one is the worker (all three workers in the repos)
    - the fourth one is the Notification Service
## How to run
    1. Clone every related repos
    2. you can create a folder and clone each one into the folder
    3. Each repos will have k8s folder
    4. go to k8s folder then configure the env and run kubectl apply -f . for each repos
    5 Sorry for inconvenience kub, pls do kubectl port-forward svc/notification-service-service 8081:80 -n default for testing, since we had a bug with socket.io connection
    6. Finish!!!
