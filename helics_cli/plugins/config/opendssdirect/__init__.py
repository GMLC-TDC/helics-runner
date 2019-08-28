# -*- coding: utf-8 -*-
import os
import shutil

from helics_cli.plugins.config.base import BaseConfig
from helics_cli.templates import ConfigGenerator
from helics_cli.utils import abs2rel, echo, mkdir

from jinja2 import Template

CURRENT_DIRECTORY = os.path.dirname(os.path.realpath(__file__))

with open(
    os.path.abspath(
        os.path.join(CURRENT_DIRECTORY, "./opendssdirect-federate-config.json")
    )
) as f:
    opendssdirect_config_template = Template(f.read())


class OpenDSSDirectConfigGenerator(ConfigGenerator):

    template = opendssdirect_config_template

    def setup(self, publications, subscriptions, **kwargs):
        for k, v in kwargs.items():
            self.config[k] = v

        self.config["name"] = kwargs["name"]
        self.config["total_time"] = kwargs["total_time"]
        self.config["step_time"] = kwargs["step_time"]
        self.config["publications"] = {}
        self.config["subscriptions"] = {}
        for k, v in publications.items():
            _object = v["mapping"].split("/")[0]
            _fieldname = v["mapping"].split("/")[1]
            helics_topic = k

            try:
                self.config["publications"][_object]
            except KeyError:
                self.config["publications"][_object] = {}

            self.config["publications"][_object][_fieldname] = helics_topic

        for k, v in subscriptions.items():
            _object = v["mapping"].split("/")[0]
            _fieldname = v["mapping"].split("/")[1]
            helics_topic = k

            try:
                self.config["subscriptions"][_object]
            except KeyError:
                self.config["subscriptions"][_object] = {}

            self.config["subscriptions"][_object][_fieldname] = helics_topic


class OpenDSSDirectConfig(BaseConfig):
    def run(self):
        for r in self.runner_items:
            self.runner.append(r)

    def setup(self):
        self.working_directory = self.config.pop("working_directory")
        self.simulation_file = self.config.pop("simulation_file")
        self.runner_items = []

        for federate_name, data in self.config.items():

            feeder_type = data.get("feeder_type", "distribution")

            assert feeder_type in [
                "distribution",
                "subtransmission",
            ], "Feeder type has to be `distribution` or `subtransmission`."

            federate_name = federate_name.replace("/", "_")
            echo(f"Setting up opendssdirect for {federate_name}")
            directory = os.path.join(self.working_directory, federate_name)
            # mkdir(directory)
            if not os.path.isabs(data["folder"]):
                data["folder"] = os.path.abspath(
                    os.path.join(os.path.dirname(self.simulation_file), data["folder"])
                )

            # TODO: not all files will be located in `folder`
            original_model = os.path.join(data["folder"], data["model"])
            working_directory_model = os.path.join(
                directory, "{}.dss".format(federate_name)
            )

            self._setup_opendssdirect(
                original_model, working_directory_model, federate_name
            )
            working_directory_folder = os.path.dirname(working_directory_model)
            g = OpenDSSDirectConfigGenerator(
                name=federate_name,
                publications=data["publications"],
                subscriptions=data["subscriptions"],
                total_time=data["total_time"],
                step_time=data["step_time"],
                filename=os.path.join(working_directory_folder, data["model"]),
            )
            g.write(
                os.path.join(
                    os.path.dirname(working_directory_model),
                    "{}.json".format(federate_name),
                )
            )

            self.runner_items.append(
                {
                    "name": federate_name,
                    "host": "localhost",
                    "exec": f"python opendssdirect-federate-{federate_name}.py {federate_name}.json",
                    "directory": abs2rel(directory, self.working_directory),
                }
            )

    def _setup_opendssdirect(
        self, original_model, working_directory_model, federate_name
    ):
        original_folder = os.path.dirname(original_model)
        working_directory_folder = os.path.dirname(working_directory_model)

        # Copy opendssdirect files from the folder
        shutil.copytree(original_folder, working_directory_folder)

        # Change opendssdirect source model file

        with open(original_model) as f:
            data = f.read()

        # TODO: any transformations on the data

        os.remove(working_directory_model)
        with open(working_directory_model, "w") as f:
            f.write(data)

        original_python_file = os.path.join(
            CURRENT_DIRECTORY, "opendssdirect-federate.py"
        )
        working_directory_python_file = os.path.join(
            working_directory_folder, f"opendssdirect-federate-{federate_name}.py"
        )
        shutil.copyfile(original_python_file, working_directory_python_file)