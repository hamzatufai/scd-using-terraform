# Commands to connect to the EC2 instance and transfer files

ssh -i "ec2-scd-snowflake-us-west-2-tf.pem" ec2-user@<EC2_PUBLIC_DNS>
scp -r -i "ec2-scd-snowflake-us-west-2-tf.pem" docker_exp ec2-user@<EC2_PUBLIC_DNS>:/home/ec2-user/docker_exp
ssh -i "ec2-scd-snowflake-us-west-2-tf.pem" ec2-user@<EC2_PUBLIC_DNS> -L 2080:localhost:2080 -L 4888:localhost:4888 -L 8050:localhost:8050

# Installing docker and docker-compose on the EC2 instance
sudo yum update -y
sudo yum install docker -y
sudo yum install -y libxcrypt-compat
sudo curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
sudo gpasswd -a $USER docker
newgrp docker
sudo systemctl start docker
sudo systemctl enable docker

# Commands to run the docker containers and access the UIs
docker --version
docker-compose --version
cd docker_exp
docker-compose up -d
docker ps
docker exec -i -t nifi bash

# Jupyter Lab at: http://localhost:4888/lab
# NiFi at:        http://localhost:2080/nifi/

mkdir FakeDataset
cd /opt/workspace/nifi/data/
