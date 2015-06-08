import json
import os

import requests

from geometry import Vector

GRAPHICS_ID_TO_FILE_JSON_URL = r"http://web.ccpgamescdn.com/ccpwgl/res/f7/f7a0af456dbc84f0_bf0856baccfddf5c72b4b7d86ed166e1.json"
TYPE_ID_TO_GRAPHICS_ID_JSON_URL = r"http://web.ccpgamescdn.com/ccpwgl/res/ac/ac21e84c3bde5dfc_0baa3bc3d5eff46148add86ff76421aa.json"

TIME_UNITS_PER_SECOND = 10000000.0

def fetch_json_from_endpoint(crest_request, target_url):
    """
    Fetches the json data from the crest endpoint.
    Stores them in a cache on disk.
    """
    file_name = target_url.split(":")[1].replace("/", "_")
    file_path = os.path.join("cache", file_name)
    if not os.path.exists("cache"):
        os.mkdir("cache")

    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            return json.loads(f.read())

    response = crest_request.get(target_url)
    result = response.json()
    with open(file_path, 'w') as f:
        f.write(json.dumps(result))

    return result

class ResourceMapper(object):
    def __init__(self):
        graphics_id_to_file_json = fetch_json_from_endpoint(requests, GRAPHICS_ID_TO_FILE_JSON_URL)
        type_id_to_graphics_id_json = fetch_json_from_endpoint(requests, TYPE_ID_TO_GRAPHICS_ID_JSON_URL)
        self.d = {
            "from_graphic_id" : {},
            "from_type_id": {},
        }
        for type_id in type_id_to_graphics_id_json.keys():
            self.d["from_type_id"][type_id] = str(graphics_id_to_file_json[str(type_id_to_graphics_id_json[type_id]["graphicID"])]["graphicFile"])
        for graphic_id in graphics_id_to_file_json.keys():
            self.d["from_graphic_id"][graphic_id] = str(graphics_id_to_file_json[graphic_id]["graphicFile"])

    def get_graphic_file_from_type_id(self, key):
        return self.d["from_type_id"][key]

    def get_graphic_file_from_graphic_id(self, key):
        return self.d["from_graphic_id"][key]


resource_mapper = ResourceMapper()

def get_str_id_from_href(href):
    return href.split("/")[-2]


def get_physics_data_from_frame(frame):
    results = []
    ship_data = frame["blueTeamShipData"] + frame["redTeamShipData"]
    for d in ship_data:
        ship_id = get_str_id_from_href(d["itemRef"]["href"])
        if "physicsData" not in d:
            continue
        physics_data = d["physicsData"]
        results.append((ship_id, [physics_data["x"], physics_data["y"], physics_data["z"]], [physics_data["vx"], physics_data["vy"], physics_data["vz"]]))
    return results


def get_missile_data_from_frame(frame):
    results = []
    ship_data = frame["blueTeamShipData"] + frame["redTeamShipData"]
    for d in ship_data:
        ship_id = str(d["itemRef"]["href"].split("/")[-2])
        if "missiles" not in d:
            continue
        missiles = d["missiles"]
        results.append((ship_id, missiles))
    return results


class FrameParser(object):
    def __init__(self, first_frame, scene_dict):
        self.scene_dict = scene_dict
        self.first_frame = first_frame
        self.active_ships = set()
        self.active_missiles = {}

    def parse_frames(self, frame=None):
        if not frame:
            frame = self.first_frame

        while True:
            self.parse_frame(frame, self.scene_dict)
            try:
                frame = fetch_json_from_endpoint(requests, frame["nextFrame"]["href"])
            except KeyError:
                break

    def parse_missiles(self, ship_id, missiles, scene_dict, current_time):
        missiles_dict = scene_dict["missiles"]
        if ship_id not in self.active_missiles:
            self.active_missiles[ship_id] = set()
        found_missiles = set()
        for missile in missiles:
            missile_id = str(missile["itemID_str"])
            physics_data = missile["physicsData"]
            location = Vector(physics_data["x"], physics_data["y"], physics_data["z"])
            velocity = Vector(physics_data["vx"], physics_data["vy"], physics_data["vz"])
            type_id = get_str_id_from_href(missile["type"]["href"])
            respath = resource_mapper.get_graphic_file_from_type_id(type_id)
            if missile_id not in missiles_dict:
                missiles_dict[missile_id] = {"owner": ship_id, "timeframes": {}, "respath": respath}
            missiles_dict[missile_id]["timeframes"].update(
            {
                current_time: {
                    "location": location,
            }})

    def parse_frame(self, frame, scene_dict):
        t = (int(frame["time_str"])/ TIME_UNITS_PER_SECOND) - scene_dict["start_time"]
        found_ships = set()
        physics_data = get_physics_data_from_frame(frame)

        for ship_id, ship_position, ship_velocity in physics_data:
            found_ships.add(ship_id)
            if ship_id not in scene_dict["ships"]:
                scene_dict["ships"][ship_id] = {}
            scene_dict["ships"][ship_id][t] = {
                "location": Vector(*ship_position),
            }

        missile_data = get_missile_data_from_frame(frame)
        for ship_id, missiles in missile_data:
            self.parse_missiles(ship_id, missiles, scene_dict, t)


def get_scene_name_from_match_json(match_json):
    return "{red} vs {blue}".format(
        red=match_json["redTeam"]["teamName"],
        blue=match_json["blueTeam"]["teamName"]
    )

def get_scene_dict(target_url):
    scene_dict = {
        "ships": {},
        "missiles": {}
    }
    match_json = fetch_json_from_endpoint(requests, target_url)

    scene_dict["scene_name"] =  get_scene_name_from_match_json(match_json)

    staticSceneData = fetch_json_from_endpoint(requests, match_json["staticSceneData"]["href"])
    ships = staticSceneData["ships"]
    scene_dict["nebula_name"] = staticSceneData["nebulaName"]

    for ship in ships:
        ship_name = ship["type"]["name"]
        ship_url = ship["item"]["href"]
        ship_item_id = get_str_id_from_href(ship_url)
        respath = resource_mapper.get_graphic_file_from_type_id(get_str_id_from_href(ship["type"]["href"]))
        scene_dict[ship_item_id] = {}
        scene_dict[ship_item_id]["respath"] = respath
        slot = 0
        scene_dict[ship_item_id]["turrets"] = {}
        for turret in ship["turrets"]:
            respath = resource_mapper.get_graphic_file_from_graphic_id(get_str_id_from_href(turret["graphicResource"]["href"]))
            scene_dict[ship_item_id]["turrets"][slot] = respath
            slot += 1

    firstReplayFrame = fetch_json_from_endpoint(requests, match_json["firstReplayFrame"]["href"])
    lastReplayFrame = fetch_json_from_endpoint(requests, match_json["lastReplayFrame"]["href"])
    scene_dict["start_time"] = int(firstReplayFrame["time_str"]) / TIME_UNITS_PER_SECOND
    scene_dict["end_time"] = int(lastReplayFrame["time_str"]) / TIME_UNITS_PER_SECOND
    scene_dict["duration"] = scene_dict["end_time"] - scene_dict["start_time"]
    frame_parser = FrameParser(firstReplayFrame, scene_dict)
    frame_parser.parse_frames()
    return scene_dict
