from .dockerspawner import DockerSpawner
from traitlets import Unicode
import json
import asyncio

class ConfigurableDockerSpawner(DockerSpawner):

    resourcetypes = {
        "S": {"mem_limit": "512M", "cpu_shares": 256},
        "M": {"mem_limit": "1G", "cpu_shares": 512},
        "L": {"mem_limit": "2G", "cpu_shares": 1024}
    }

    repolocation = Unicode(
        "",
        help="""The location of the repository with the json files and notebooks
        """,
        config=True,
    )

    # repolocation = '/home/tneutens/Documents/UGent/Onderwijs/KIKS/server/PythonNotebooks/'
    defaultImageName = 'jupyter/scipy-notebook:latest'
        
    async def start(self, image=None, extra_create_kwargs=None, extra_host_config=None):

        self.log.warning("######################################START2####################################")
        """Start the single-user server in a docker container.

        Additional arguments to create/host config/etc. can be specified
        via .extra_create_kwargs and .extra_host_config attributes.

        If the container exists and `c.DockerSpawner.remove` is true, then
        the container is removed first. Otherwise, the existing containers
        will be restarted.
        """

        # Get the identifier of the container (defined in our json file)
        container_id = self.user_options.get('id')  # TODO: Get this through the request sent to the hub's api
        self.log.warning("The user_options contain {}".format(self.user_options))

        # Read json file
        json_config = self.read_json_containerinfo()
        if (container_id not in json_config):
            self.log.warning("The specified containerid does not exist, running default container.")
            container_id = "1"

        # Update the notebook directory where the file tree will open if it is present in the json config
        self.update_notebook_dir(json_config, container_id) 

        if image:
            self.log.warning("Specifying image via .start args is deprecated")
            self.image = image
        if extra_create_kwargs:
            self.log.warning(
                "Specifying extra_create_kwargs via .start args is deprecated"
            )
            self.extra_create_kwargs.update(extra_create_kwargs)
        if extra_host_config:
            self.log.warning(
                "Specifying extra_host_config via .start args is deprecated"
            )
            self.extra_host_config.update(extra_host_config)
        

        # image priority:
        # 1. user options (from spawn options form)
        # 2. self.image from config
        self.image = self.extract_image_for_container(json_config, container_id)

        await self.pull_image(self.image)
        
        # Get memory setting from config file
        memory_setting = self.extract_from_json(json_config, container_id, "Resource") # TODO handle None when there is no Resource key in the json file
        self.mem_limit = self.resourcetypes[memory_setting]["mem_limit"]
        self.cpu_shares = self.resourcetypes[memory_setting]["cpu_shares"]

        obj = await self.get_object()
        if obj and self.remove:
            self.log.warning(
                "Removing %s that should have been cleaned up: %s (id: %s)",
                self.object_type,
                self.object_name,
                self.object_id[:7],
            )
            await self.remove_object()

        obj = await self.create_object()
        self.object_id = obj[self.object_id_key]
        self.log.info(
            "Created %s %s (id: %s) from image %s",
            self.object_type,
            self.object_name,
            self.object_id[:7],
            self.image,
        )

        # TODO: handle unpause
        self.log.info(
            "Starting %s %s (id: %s)",
            self.object_type,
            self.object_name,
            self.container_id[:7],
        )

        

        # start the container
        await self.start_object()

        basepath = "/home/jovyan/"
        for file in self.extract_from_json(json_config, container_id, "Files"):
            # Create folder structure for file
            cmd = "docker exec " + self.object_name + " mkdir -p -m 755 " + basepath + file[:file.rfind('/')] 
            stdout, stderr = await self.execute_command(cmd)
            self.log.info("Stdout: %s \\nStderr: %s", stdout, stderr)
            # Copy file to container
            cmd = "docker cp " + self.repolocation + file + " " + self.object_name + ":" + basepath + file
            stdout, stderr = await self.execute_command(cmd)
            self.log.info("Stdout: %s \\nStderr: %s", stdout, stderr)
            # change file owner
            cmd = "docker exec " + self.object_name + " chown jovyan:users " + basepath + file
            stdout, stderr = await self.execute_command(cmd)
            self.log.info("Stdout: %s \\nStderr: %s", stdout, stderr)

        
            
        ip, port = await self.get_ip_and_port()
        self.user.server.ip = ip
        self.user.server.port = port

        return (ip, port)


    def options_from_query(self, query_data):
        self.log.warning("Query data = {}".format(query_data))
        #self.user_options = query_data
        return self.options_from_form(query_data)

    def options_from_form(self, formdata):
        """Turn options formdata into user_options"""
        options = {}
        if 'id' in formdata:
            options['id'] = formdata['id'][0]
        return options

    def update_notebook_dir(self, json_config, container_id):
        if self.extract_from_json(json_config, container_id, "BasePath") is not None:
            self.notebook_dir = self.extract_from_json(json_config, container_id, "BasePath")

    def read_json_containerinfo(self):
        js = {}
        with open(self.repolocation + "PythonNotebooks.json") as jsonfile:
            js = json.load(jsonfile)
        return js   

    def extract_from_json(self, json_obj, id, type):
        if type in json_obj[id]:
            return json_obj[id][type]
        else: 
            return None

    def extract_image_for_container(self, json_obj, id):
        if "ImageName" in json_obj[id]:
            return json_obj[id]["ImageName"] 
        else:
            return self.defaultImageName   


    async def execute_command(self, cmd):
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE)

        # do something else while ls is working

        # if proc takes very long to complete, the CPUs are free to use cycles for 
        # other processes
        return await proc.communicate()
        #stdout, stderr = await proc.communicate()


    async def post_start_exec(self, cmd):
        """
        Execute additional command inside the container after starting it.

        e.g. calling 'docker exec'
        """

        container = await self.get_object()
        container_id = container[self.object_id_key]

        exec_kwargs = {'cmd': self.post_start_cmd, 'container': container_id}

        exec_id = await self.docker("exec_create", **exec_kwargs)

        return self.docker("exec_start", exec_id=exec_id)


    async def create_object(self):
        """Create the container/service object"""
        create_kwargs = dict(
            image=self.image,
            environment=self.get_env(),
            volumes=self.volume_mount_points,
            name=self.container_name,
            command=(await self.get_command() + ["--NotebookApp.allow_hidden=True", "--ContentsManger.allow_hidden=True", "--TreeHandler.allow_hidden=False", "--FileContentsManager.allow_hidden=False", "--AuthenticatedFileHandler.allow_hidden=True", "--NotebookApp.allow_origin='*'"])
        )

        # ensure internal port is exposed
        create_kwargs["ports"] = {"%i/tcp" % self.port: None}

        create_kwargs.update(self._render_templates(self.extra_create_kwargs))

        # build the dictionary of keyword arguments for host_config
        host_config = dict(
            auto_remove=self.remove,
            binds=self.volume_binds,
            links=self.links,
            mounts=self.mount_binds,
            mem_limit=self.mem_limit,
            cpu_shares=self.cpu_shares
        )

        if getattr(self, "mem_limit", None) is not None:
            # If jupyterhub version > 0.7, mem_limit is a traitlet that can
            # be directly configured. If so, use it to set mem_limit.
            # this will still be overriden by extra_host_config
            host_config["mem_limit"] = self.mem_limit

        if not self.use_internal_ip:
            host_config["port_bindings"] = {self.port: (self.host_ip,)}
        host_config.update(self._render_templates(self.extra_host_config))
        host_config.setdefault("network_mode", self.network_name)


        self.log.debug("Starting host with config: %s", host_config)
        self.log.debug("Starting container with config: %s", create_kwargs)

        host_config = self.client.create_host_config(**host_config)
        create_kwargs.setdefault("host_config", {}).update(host_config)

        # create the container
        obj = await self.docker("create_container", **create_kwargs)
        return obj