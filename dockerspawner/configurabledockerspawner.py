from dockerspawner import DockerSpawner
import json
import asyncio

class ConfigurableDockerSpawner(DockerSpawner):
    
    async def start(self, image=None, extra_create_kwargs=None, extra_host_config=None):
        """Start the single-user server in a docker container.

        Additional arguments to create/host config/etc. can be specified
        via .extra_create_kwargs and .extra_host_config attributes.

        If the container exists and `c.DockerSpawner.remove` is true, then
        the container is removed first. Otherwise, the existing containers
        will be restarted.
        """

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

        
        # Get the identifier of the container (defined in our json file)
        container_id = self.user_options.get('id')

        # Read json file
        json_config = self.read_json_containerinfo()
        if (container_id not in json_config):
            self.log.warning("The specified containerid does not exist, running default container.")

        # image priority:
        # 1. user options (from spawn options form)
        # 2. self.image from config
        self.image = self.extract_image_for_container(json_config, container_id)

        await self.pull_image(self.image)
        
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

        for file in json_config[container_id]["Files"]:
            cmd = "docker cp " + self.repolocation + file + " " + self.object_name + ":/" + "~" # TODO path in container

        ip, port = await self.get_ip_and_port()
        if jupyterhub.version_info < (0, 7):
            # store on user for pre-jupyterhub-0.7:
            self.user.server.ip = ip
            self.user.server.port = port
        # jupyterhub 0.7 prefers returning ip, port:
        return (ip, port)


    def read_json_containerinfo(self):
        js = {}
        with open("./test.json") as jsonfile:
            js = json.load(jsonfile)
        return js   

    def extract_files_from_json(self, json_obj, id):
        return json_obj[id]["Files"]

    def extract_resource(self, json_obj, id):
        return json_obj[id]["Resource"]

    def extract_image_for_container(self, json_obj, id):
        if "ImageName" in json_obj[id]:
            return json_obj[id]["ImageName"] 
        else:
            return self.defaultImageName    # TODO: add this setting to the global config file (jupyterhub_config.py)


    async def execute_command(self, cmd):
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE)

        # do something else while ls is working

        # if proc takes very long to complete, the CPUs are free to use cycles for 
        # other processes
        return proc.communicate()
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