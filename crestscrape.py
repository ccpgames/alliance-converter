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


def get_effect_data_from_frame(frame):
        results = []
        ship_data = frame["blueTeamShipData"] + frame["redTeamShipData"]
        for d in ship_data:
            ship_id = get_str_id_from_href(d["itemRef"]["href"])
            if "effects" not in d:
                continue
            effects = d["effects"]
            results.append((ship_id, effects))
        return results


class FrameParser(object):
    def __init__(self, first_frame, scene_dict):
        self.scene_dict = scene_dict
        self.first_frame = first_frame
        self.effects_processed = []

    def parse_frames(self, frame=None):
        if not frame:
            frame = self.first_frame

        while True:
            self.parse_frame(frame, self.scene_dict)
            try:
                frame = fetch_json_from_endpoint(requests, frame["nextFrame"]["href"])
            except KeyError:
                break

    def parse_effects(self, ship_id, effects, scene_dict, current_time):
        projectile_dict = scene_dict["projectiles"]
        for effect in effects:
            firing_effects = ("effects.ProjectileFired", "effects.MissileDeployment")
            if effect["guid"] in firing_effects:
                start_time = (effect["startTime"] / TIME_UNITS_PER_SECOND) - scene_dict["start_time"]
                target_id = str(effect["targetID_str"])
                graphic_id = get_str_id_from_href(effect["ammoGraphicResource"]["href"])

                comparable_tuple = (effect["guid"], start_time, graphic_id, ship_id, target_id)
                if comparable_tuple in self.effects_processed:
                    continue
                try:
                    ammo_graphic_resource = resource_mapper.get_graphic_file_from_graphic_id(graphic_id)
                except KeyError:
                    print "Graphic id", graphic_id, "not found, using default."
                    ammo_graphic_resource = resource_mapper.get_graphic_file_from_graphic_id("20043")
                if start_time not in projectile_dict:
                    projectile_dict[start_time] = []
                slots = []
                for module in effect["modules"]:
                    module_id = module["moduleID_str"]
                    slots.append(scene_dict[ship_id]["turret_module_id_to_slot"][module_id])


                self.effects_processed.append(comparable_tuple)

                projectile_dict[start_time].append({
                  "source_id": str(ship_id),
                  "target_id": target_id,
                  "slots": slots,
                  "ammo_graphic_resource": ammo_graphic_resource,
                })

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

        effect_data = get_effect_data_from_frame(frame)
        for ship_id, effects in effect_data:
            self.parse_effects(ship_id, effects, scene_dict, t)


def get_scene_name_from_match_json(match_json):
    return "{red} vs {blue}".format(
        red=match_json["redTeam"]["teamName"],
        blue=match_json["blueTeam"]["teamName"]
    )

def get_scene_dict(target_url):
    scene_dict = {
        "ships": {},
        "projectiles": {}
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
        scene_dict[ship_item_id]["turret_module_id_to_slot"] = {}
        for turret in ship["turrets"]:
            respath = resource_mapper.get_graphic_file_from_graphic_id(get_str_id_from_href(turret["graphicResource"]["href"]))
            module_id = get_str_id_from_href(turret["href"])
            scene_dict[ship_item_id]["turret_module_id_to_slot"][module_id] = slot
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
