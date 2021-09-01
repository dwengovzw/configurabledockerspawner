# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

# Configuration file for JupyterHub
#import os
from jupyter_client.localinterfaces import public_ips
import tmpauthenticator 


c = get_config()
ip = public_ips()[0]
#print("---------------------- PUBLIC IP: {} --------------------".format(ip))

c.ConfigurableHTTPProxy.api_url = 'http://127.0.0.1:5432'


c.LocalAuthenticator.create_system_users = True

c.Authenticator.allowed_users = {'tneutens', 'service-admin', 'ilearn', 'dwengo'}
c.Authenticator.admin_user = {'tneutens', 'service-admin'}

c.JupyterHub.base_url = '/jupyterhub/'
c.JupyterHub.admin_users = {"service-admin", 'tneutens'}
c.JupyterHub.api_tokens = {
    "2f482d5b5f336d43806e2469b550509f403e075e4d30bee81583eb85ec0586d3": "service-admin",
}

c.JupyterHub.api_tokens = {
    "9083e257ac7518c73b1ad2e0764dcefa33a65afa2bb5249363c211f842835f41": "ilearn",
}

c.JupyterHub.api_tokens = {
    "6d5d503af19e3db21fd7f40f980ac5a69c1dfedb40ae8871d21e9b1d15de4932": "dwengo",
}

c.JupyterHub.authenticator_class = tmpauthenticator.TmpAuthenticator

#c.TmpAuthenticator.force_new_server = True 


c.JupyterHub.services = [
    {"name": "test-service", "api_token": "dd9403aeb4d473b2d99178229a0a21504b1c156d40e03dd51c7c653fc6c89c3c", "admin": True,}
]

# We rely on environment variables to configure JupyterHub so that we
# avoid having to rebuild the JupyterHub container every time we change a
# configuration parameter.
       

# Spawn single-user servers as Docker containers
c.JupyterHub.spawner_class = 'configurabledockerspawner.ConfigurableDockerSpawner'
#c.JupyterHub.spawner_class = 'dockerspawner.DockerSpawner'




# Spawn containers from this image
#c.DockerSpawner.container_image = 'jupyter/scipy-notebook:latest'
# JupyterHub requires a single-user instance of the Notebook server, so we
# default to using the `start-singleuser.sh` script included in the
# jupyter/docker-stacks *-notebook images as the Docker run command when
# spawning containers.  Optionally, you can override the Docker run command
# using the DOCKER_SPAWN_CMD environment variable.

# Explicitly set notebook directory because we'll be mounting a host volume to
# it.  Most jupyter/docker-stacks *-notebook images run the Notebook server as
# user `jovyan`, and set the notebook directory to `/home/jovyan/work`.
# We follow the same convention.
notebook_dir = '/home/jovyan'
c.Spawner.notebook_dir = notebook_dir
# Remove containers once they are stopped
c.ConfigurableDockerSpawner.remove_containers = True
c.ConfigurableDockerSpawner.remove = True 

# For debugging arguments passed to spawned containers
c.ConfigurableDockerSpawner.debug = True

# For setting the repository location with the Python notebooks
c.ConfigurableDockerSpawner.repolocation = '/root/PythonNotebooks/'

# User containers will access hub by container name on the Docker network
c.JupyterHub.hub_ip = ip
c.JupyterHub.hub_port = 9000
c.NotebookApp.allow_hidden = True
c.ContentsManger.allow_hidden = True
c.FileContentsManager.allow_hidden = True


c.ConfigurableDockerSpawner.mem_limit = '2G'

#c.Spawner.container_image = 'jupyter/scipy-notebook:latest'


c.Application.log_level = 'DEBUG'

