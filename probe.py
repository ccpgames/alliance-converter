import yaml

class SceneFile(object):
    def __init__(self):
        self.data = {
            "name": "untitled",
            "description": "Autogenerated scene file",
            "commands": []
        }

    def display(self):
        print yaml.dump(self.data, default_flow_style=False)

    def set_name(self, name):
        self.data["name"] = name

    def add_command(self, command):
        self.data["commands"].append(command)

    def add_actor(self, actor_id, res_path):
        self.add_command(["actor", str(actor_id), res_path])
        self.add_command(["add_actor", str(actor_id)])

    def remove_actor(self, actor_id):
        self.add_command(["remove_actor", str(actor_id)])

    def fit_turret_to_actor(self, actor_id, res_path, slot):
        self.add_command(["fit_turret", str(actor_id), res_path, slot])

    def set_actor_position(self, actor_id, position):
        self.add_command(["set_position", str(actor_id), position.to_list()])

    def move_actor_to(self, actor_id, position, duration):
        self.add_command(["move_to", str(actor_id), position.to_list(), duration])

    def add_sleep(self, duration):
        self.add_command(["sleep", duration])

    def add_timed_events(self, timed_events):
        event_times = sorted(timed_events.keys())
        last_time = 0.0
        for time in event_times:
            if time > last_time:
                self.add_sleep(time - last_time)
                last_time = time
            for event in timed_events[time]:
                self.add_command(event)

    def save(self, file_path):
        with open(file_path, "w") as f:
            f.write(yaml.dump(self.data))
