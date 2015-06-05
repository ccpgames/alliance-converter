import argparse
import os
import math
import random

import crestscrape
import geometry
import red
import probe

DESCRIPTION= "A tool to generate EveProbe scene files from alliance tournament \
data that is fetched through public CREST."


def get_closest_ship_at_timeframe(scene_dict, p, timeframe):
    closest = None
    min_distance = -1
    for ship_id in scene_dict["ships"]:
        ship_dict = scene_dict["ships"][ship_id]
        if timeframe not in ship_dict:
            continue
        ship_position_vector = ship_dict[timeframe]["location"]
        distance = (ship_position_vector - p).length_squared()
        if closest is None or distance < min_distance:
            min_distance = distance
            closest = ship_id
    return closest


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


def create_scene_file_header(scene_dict, scene_file):
    scene_file.set_name(scene_dict["scene_name"])
    scene_file.add_command(["scene", "m10"])
    scene_file.add_command(["camera", "main", 1.57, 3.0, 100000.0])
    position, interest = get_starting_camera_position_and_interest(scene_dict)
    scene_file.add_command(["set_position", "main", position])
    scene_file.add_command(["set_interest", "main", interest])
    scene_file.add_command(["select_camera", "main"])


def fit_turrets_to_ship(scene_dict, scene_file, ship_id):
    for slot, respath in scene_dict[ship_id]["turrets"].iteritems():
        scene_file.fit_turret_to_actor(ship_id, respath, slot)


def initialize_ship_red_file(scene_dict, red_file, ship_id):
    ship_dict = scene_dict["ships"][ship_id]
    frames = sorted(ship_dict.keys())
    start_time = frames[0]
    end_time = frames[-1]

    start_pos = ship_dict[start_time]["location"]
    end_pos = ship_dict[end_time]["location"]

    red_file.add_vector_curve(ship_id, 0.0, (end_time - start_time), start_pos, end_pos)
    start_direction = ship_dict[frames[1]]["location"] - ship_dict[frames[0]]["location"]
    end_direction = ship_dict[frames[-1]]["location"] - ship_dict[frames[-2]]["location"]
    red_file.add_rotation_curve(ship_id, 0.0, (end_time - start_time), start_direction, end_direction)


    last_time = start_time
    for time in frames:
        red_file.add_vector_key(ship_id, ship_dict[time]["location"], time)
        playback_velocity = ship_dict[time]["location"] - ship_dict[last_time]["location"]
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


def add_initial_scene_data(scene_dict, scene_file, red_file):
    for ship_id in scene_dict["ships"]:
        initialize_ship_scene_file(scene_dict, scene_file, ship_id)
        initialize_ship_red_file(scene_dict, red_file, ship_id)
    scene_name = scene_dict["scene_name"]
    scene_file.add_command(["bind_matching_dynamics", "res:/curves/{scene_name}.red".format(scene_name=scene_name)])


def wait_for_loads(scene_file):
    scene_file.add_command(["preload_lods"])
    scene_file.add_command(["wait_for_loads"])


def add_timed_events(scene_dict, scene_file):
    timed_events = {}
    missiles_dict = scene_dict["missiles"]
    for missile_id in missiles_dict:
        missile_dict = missiles_dict[missile_id]
        timeframes = sorted(missile_dict["timeframes"])
        first_frame = timeframes[0]
        last_frame = timeframes[-1]
        last_location = missile_dict["timeframes"][last_frame]["location"]
        target = get_closest_ship_at_timeframe(scene_dict, last_location, last_frame)
        if first_frame not in timed_events:
            timed_events[first_frame] = []

        turrets = scene_dict[missile_dict["owner"]]["turrets"]
        slot = random.randint(0, len(turrets) - 1)
        slots = [slot]
        repeat_rate = 0
        timed_events[first_frame].append(["fire_missile", missile_dict["owner"], slots, target, missile_dict["respath"], repeat_rate])

    scene_file.add_timed_events(timed_events)


def save(scene_file, red_file, save_folder, scene_name):
    scene_save_folder_path = os.path.join(save_folder, "sequences")
    scene_save_path = os.path.join(scene_save_folder_path, "{scene_name}.yaml".format(scene_name=scene_name))
    if not os.path.exists(scene_save_folder_path):
        os.mkdir(scene_save_folder_path)
    red_save_folder_path = os.path.join(save_folder, "curves")
    if not os.path.exists(red_save_folder_path):
        os.mkdir(red_save_folder_path)
    red_save_path = os.path.join(red_save_folder_path, "{scene_name}.red".format(scene_name=scene_name))
    scene_file.save(scene_save_path)
    red_file.save(red_save_path)


def main(save_folder):
    scene_file = probe.SceneFile()
    red_file = red.RedFile()
    print "Loading or fetching scene data"
    scene_dict = crestscrape.get_scene_dict()
    scene_name = scene_dict["scene_name"]
    print "Generating scene for", scene_name

    create_scene_file_header(scene_dict, scene_file)
    add_initial_scene_data(scene_dict, scene_file, red_file)
    wait_for_loads(scene_file)
    add_timed_events(scene_dict, scene_file)

    print "Saving"
    save(scene_file, red_file, save_folder, scene_name)
    print "Done"


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("save_folder", help="A directory in which to save the generated scene data", default=".", nargs="?")
    args = parser.parse_args()
    main(args.save_folder)