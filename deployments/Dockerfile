

FROM python:3.7.8-buster

# CHANGE SOURCE
RUN sed -i "s@http://deb.debian.org@https://mirrors.163.com@g" /etc/apt/sources.list


#INSTALL REQUREMENTS
ADD ./deployments/pip.conf /etc/
COPY ./requirements.txt  /home/
RUN pip install -r /home/requirements.txt


#INSTALL REDIS
RUN apt-get update
RUN apt-get install -y redis-server
RUN apt-get install -y nginx
ARG redis_conf_path=/etc/redis/redis.conf
RUN sed -i 's/daemonize no/daemonize yes/g' $redis_conf_path
RUN sed -i 's/bind 127.0.0.1/bind 0.0.0.0/g' $redis_conf_path


#COPY SOURCE CODE
COPY ./ /home/src
COPY ./deployments/default /etc/nginx/sites-enabled/default
COPY ./deployments/run.sh /home/
RUN chmod +x /home/run.sh
RUN sed -i -e 's/\r$//' /home/run.sh

WORKDIR /home/src

# setting logs
#RUN mkdir logs
#RUN ln -sf /dev/stdout /var/log/nginx/access.log
#RUN ln -sf /dev/stdout /home/src/logs/django.log
#RUN ln -sf /dev/stdout /home/src/logs/wechat.log
#RUN ln -sf /dev/stdout /home/src/logs/uwsgi.log



EXPOSE 80

CMD ["/home/run.sh"]