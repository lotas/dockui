bubble tea ui gui https://github.com/charmbracelet/bubbletea

disk usage: docker

# Docker API


```sh
curl --unix-socket /var/run/docker.sock -X GET http://localhost/info
```


# Docker

```sh
docker system prune

docker system df -v

docker rmi $(docker images -q --no-trunc)

docker volume prune

```

# Python

`pip install docker`
