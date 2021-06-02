from dockerspawner import DockerSpawner
import json
import asyncio

class ConfigurableDockerSpawner(DockerSpawner):

    resourcetypes = {
        "S": {"mem_limit": "512M", "cpu_shares": 256},
        "M": {"mem_limit": "1G", "cpu_shares": 512},
        "L": {"mem_limit": "2G", "cpu_shares": 1024}
    }

    repolocation = '/home/tneutens/Documents/UGent/Onderwijs/KIKS/server/PythonNotebooks/'
    defaultImageName = 'jupyter/scipy-notebook:latest'
        
    async def start(self, image=None, extra_create_kwargs=None, extra_host_config=None):

        self.log.warning("######################################START####################################")
        self.log.warning(ConfigurableDockerSpawner)
        self.log.warning(self)
        """Start the single-user server in a docker container.

        Additional arguments to create/host config/etc. can be specified
        via .extra_create_kwargs and .extra_host_config attributes.

        If the container exists and `c.DockerSpawner.remove` is true, then
        the container is removed first. Otherwise, the existing containers
        will be restarted.
        """

        # Get the identifier of the container (defined in our json file)
        container_id = "1" # self.user_options.get('id')  # TODO: Get this through the request sent to the hub's api

        # Read json file
        json_config = self.read_json_containerinfo()
        if (container_id not in json_config):
            self.log.warning("The specified containerid does not exist, running default container.")

        self.notebook_dir = self.extract_from_json(json_config, container_id, "BasePath")

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
        memory_setting = self.extract_from_json(json_config, container_id, "Resource")
        self.mem_limit = self.resourcetypes[memory_setting]["mem_limit"]
        self.cpu_shares = self.resourcetypes[memory_setting]["cpu_shares"]

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


    def read_json_containerinfo(self):
        js = {}
        with open(self.repolocation + "PythonNotebooks.json") as jsonfile:
            js = json.load(jsonfile)
        return js   

    def extract_from_json(self, json_obj, id, type):
        return json_obj[id][type]

    # def extract_files_from_json(self, json_obj, id):
    #     return json_obj[id]["Files"]

    # def extract_resource(self, json_obj, id):
    #     return json_obj[id]["Resource"]

    # def extract_base_path(self, json_obj, id):
    #     return json_obj[id]["BasePath"]

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