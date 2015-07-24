import argparse
import os

import crestscrape
import geometry
import red
import probe

DESCRIPTION= "A tool to generate EveProbe scene files from alliance tournament \
data that is fetched through public CREST."


def get_starting_camera_position_and_interest(scene_dict):
    ships_counted = 0
    accumulation_vector = geometry.Vector(0.0, 0.0, 0.0)
    for ship_id in scene_dict["ships"]:
        ship_dict = scene_dict["ships"][ship_id]
        first = min(ship_dict.keys())
        accumulation_vector = ship_dict[first]["location"]
        ships_counted += 1
    interest =  accumulation_vector / ships_counted
    position = interest - geometry.Vector(1000.0, 0.0, 0.0)
    return position.to_list(), interest.to_list()


def create_scene_file_header(scene_dict, scene_file, ship_to_follow):
    scene_file.set_name(scene_dict["scene_name"])
    scene_file.add_command(["scene", scene_dict["nebula_name"]])
    scene_file.add_command(["camera", "main", 1.57, 3.0, 100000.0])
    position, interest = get_starting_camera_position_and_interest(scene_dict)
    scene_file.add_command(["set_position", "main", position])
    scene_file.add_command(["set_interest", "main", interest])
    scene_file.add_command(["select_camera", "main"])
    if ship_to_follow is not None:
        scene_file.add_command(["add_behavior", "main", "Follow", ship_to_follow, 300])


def fit_turrets_to_ship(scene_dict, scene_file, ship_id):
    for slot, respath in scene_dict[ship_id]["turrets"].iteritems():
        scene_file.fit_turret_to_actor(ship_id, respath, slot)


def initialize_actor_red_file(actor_dict, red_file, ship_id):
    frames = sorted(actor_dict.keys())
    start_time = frames[0]
    end_time = frames[-1]

    start_pos = actor_dict[start_time]["location"]
    end_pos = actor_dict[end_time]["location"]

    red_file.add_vector_curve(ship_id, 0.0, (end_time - start_time), start_pos, end_pos)
    start_direction = actor_dict[frames[1]]["location"] - actor_dict[frames[0]]["location"]
    end_direction = actor_dict[frames[-1]]["location"] - actor_dict[frames[-2]]["location"]
    red_file.add_rotation_curve(ship_id, 0.0, (end_time - start_time), start_direction, end_direction)


    last_time = start_time
    for time in frames:
        red_file.add_vector_key(ship_id, actor_dict[time]["location"], time)
        playback_velocity = actor_dict[time]["location"] - actor_dict[last_time]["location"]
        rotation_time = 0.001
        red_file.add_rotation_key(ship_id, playback_velocity, last_time + rotation_time / 2.0)
        red_file.add_rotation_key(ship_id, playback_velocity, time - rotation_time / 2.0)
        last_time = time


def initialize_ship_scene_file(scene_dict, scene_file, ship_id):
    ship_dict = scene_dict["ships"][ship_id]
    frames = sorted(ship_dict.keys())
    start_time = frames[0]
    ship_position = ship_dict[start_time]["location"]
    scene_file.add_actor(ship_id, scene_dict[ship_id]["respath"])
    scene_file.set_actor_position(ship_id, ship_position)

    fit_turrets_to_ship(scene_dict, scene_file, ship_id)

def initialize_drone_scene_file(scene_dict, scene_file, drone_id):
    location_dict = scene_dict["drones"]["locations"][drone_id]
    frames = sorted(location_dict.keys())
    start_time = frames[0]
    start_position = location_dict[start_time]["location"]
    scene_file.add_command(["actor", drone_id, str(scene_dict["drones"][drone_id]["type_data"]["graphicID"]["sofDNA"])])
    scene_file.set_actor_position(drone_id, start_position)


def add_initial_scene_data(scene_dict, scene_file, red_file):
    for ship_id in scene_dict["ships"]:
        initialize_ship_scene_file(scene_dict, scene_file, ship_id)
        actor_dict = scene_dict["ships"][ship_id]
        initialize_actor_red_file(actor_dict, red_file, ship_id)
    for drone_id in scene_dict["drones"]["locations"]:
        initialize_drone_scene_file(scene_dict, scene_file, drone_id)
        actor_dict = scene_dict["drones"]["locations"][drone_id]
        initialize_actor_red_file(actor_dict, red_file, drone_id)

    scene_name = scene_dict["scene_name"]
    scene_file.add_command(["bind_matching_dynamics", "res:/curves/{scene_name}.red".format(scene_name=scene_name)])


def wait_for_loads(scene_file):
    scene_file.add_command(["preload_lods"])
    scene_file.add_command(["wait_for_loads"])


def add_timed_events(scene_dict, scene_file):
    timed_events = {}

    effects_dict = scene_dict["projectiles"]
    for time_frame in effects_dict:
        for firing_dict in effects_dict[time_frame]:
            source = firing_dict["source_id"]
            target = firing_dict["target_id"]
            slots = firing_dict["slots"]
            ammo_graphic_resource = firing_dict["ammo_graphic_resource"]
            if time_frame not in timed_events:
                timed_events[time_frame] = []
            for slot in slots:
                timed_events[time_frame].append(["fire", source, slot, target, 0.0, ammo_graphic_resource])

    ship_removal_dict = scene_dict["removed_ships"]

    for time_frame in ship_removal_dict:
        if time_frame not in timed_events:
            timed_events[time_frame] = []
        for actor in ship_removal_dict[time_frame]:
            explosion_resource_path = scene_dict[actor]["explosion"]["path"]
            explosion_scale = scene_dict[actor]["explosion"]["scale"]
            timed_explosion = ["explosion_for_actor", "explosion", explosion_resource_path, actor, explosion_scale]
            timed_removal = ["remove_actor", actor]
            timed_events[time_frame].append(timed_explosion)
            removal_time_frame = time_frame + 0.1
            if removal_time_frame not in timed_events:
                timed_events[removal_time_frame] = []
            timed_events[removal_time_frame].append(timed_removal)

    drone_addition_dict = scene_dict["added_drones"]
    for time_frame in drone_addition_dict:
        if time_frame not in timed_events:
            timed_events[time_frame] = []
        for drone_id in drone_addition_dict[time_frame]:
            add_command = ["add_actor", drone_id]
            timed_events[time_frame].append(add_command)

    drone_removal_dict = scene_dict["removed_drones"]
    for time_frame in drone_removal_dict:
        if time_frame not in timed_events:
            timed_events[time_frame] = []
        for drone_id in drone_removal_dict[time_frame]:
            removal_command = ["remove_actor", drone_id]
            timed_events[time_frame].append(removal_command)

    scene_file.add_timed_events(timed_events)


def save(scene_file, red_file, save_folder, scene_name):
    scene_save_folder_path = os.path.join(save_folder, "sequences")
    scene_save_path = os.path.join(scene_save_folder_path, "{scene_name}.yaml".format(scene_name=scene_name))
    if not os.path.exists(scene_save_folder_path):
        os.makedirs(scene_save_folder_path)
    red_save_folder_path = os.path.join(save_folder, "curves")
    if not os.path.exists(red_save_folder_path):
        os.mkdir(red_save_folder_path)
    red_save_path = os.path.join(red_save_folder_path, "{scene_name}.red".format(scene_name=scene_name))
    scene_file.save(scene_save_path)
    red_file.save(red_save_path)


def main(target_url, save_folder, ship_to_follow):
    scene_file = probe.SceneFile(ship_to_follow)
    red_file = red.RedFile()
    print "Loading or fetching scene data"
    scene_dict = crestscrape.get_scene_dict(target_url)
    scene_name = scene_dict["scene_name"]
    print "Generating scene for", scene_name

    create_scene_file_header(scene_dict, scene_file, ship_to_follow)
    add_initial_scene_data(scene_dict, scene_file, red_file)
    wait_for_loads(scene_file)
    add_timed_events(scene_dict, scene_file)

    print "Saving"
    save(scene_file, red_file, save_folder, scene_name)
    print "Done"


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("target_url", help="The url that points to the tournament match endpoint")
    parser.add_argument("save_folder", help="A directory in which to save the generated scene data", default=".", nargs="?")
    parser.add_argument("-f", "--follow", help="The item-id of a ship that the camera should follow ", default=None, nargs="?")
    args = parser.parse_args()
    main(args.target_url, args.save_folder, args.follow)
