import json
import os

import requests
import urlparse

from geometry import Vector

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

    if "/eve/graphics/" in target_url:
        target_url = target_url.replace("/eve/graphics/", "/graphicids/")
    print "Fetching", target_url
    response = crest_request.get(target_url)
    result = response.json()
    with open(file_path, 'w') as f:
        f.write(json.dumps(result))

    return result


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


def get_drone_data_from_frame(frame):
    results = []
    ship_data = frame["blueTeamShipData"] + frame["redTeamShipData"]
    for d in ship_data:
        ship_id = get_str_id_from_href(d["itemRef"]["href"])
        if "drones" not in d:
            continue
        drones = d["drones"]
        results.append((ship_id, drones))
    return results


def get_graphic_file_from_graphic_id(base_url, graphic_id_str):
    path = "/graphicids/%s/" % graphic_id_str
    target_url = urlparse.urljoin(base_url, path)
    graphic_id_data = fetch_json_from_endpoint(requests, target_url)
    return graphic_id_data["graphicFile"]


class FrameParser(object):
    def __init__(self, crest_base_url, first_frame, scene_dict):
        self.crest_base_url = crest_base_url
        self.scene_dict = scene_dict
        self.first_frame = first_frame
        self.effects_processed = []
        self.active_ships = set()
        self.active_drones = set()

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
                    ammo_graphic_resource = get_graphic_file_from_graphic_id(self.crest_base_url, graphic_id)
                except KeyError:
                    print "Graphic id", graphic_id, "not found, using default."
                    ammo_graphic_resource = get_graphic_file_from_graphic_id(self.crest_base_url, "20043")
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

    def update_active_ships(self, ships_this_frame, scene_dict, current_time):
        removed_ships = self.active_ships - ships_this_frame
        self.active_ships = ships_this_frame
        if not removed_ships:
            return
        scene_dict["removed_ships"][current_time] = list(removed_ships)

    def update_active_drones(self, drones_this_frame, scene_dict, current_time):
        added_drones = drones_this_frame - self.active_drones
        removed_drones = self.active_drones - drones_this_frame
        self.active_drones = drones_this_frame
        scene_dict["removed_drones"][current_time] = list(removed_drones)
        scene_dict["added_drones"][current_time] = list(added_drones)

    def parse_drones(self, ship_id, drones, scene_dict, current_time, found_drones):
        for drone in drones:
            item_id = str(drone["itemID"])
            physics_data = drone["physicsData"]
            if item_id not in found_drones:
                found_drones.add(item_id)
            if item_id not in scene_dict["drones"]:
                scene_dict["drones"][item_id] = {}
            if item_id not in scene_dict["drones"]["locations"]:
                scene_dict["drones"]["locations"][item_id] = {}
            scene_dict["drones"]["locations"][item_id][current_time] = {
                "location": Vector(physics_data["x"], physics_data["y"], physics_data["z"]),
            }
            scene_dict["drones"][item_id]["type_data"] = fetch_json_from_endpoint(requests, drone["type"]["href"])

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
        self.update_active_ships(found_ships, scene_dict, t)

        effect_data = get_effect_data_from_frame(frame)
        for ship_id, effects in effect_data:
            self.parse_effects(ship_id, effects, scene_dict, t)

        drone_data = get_drone_data_from_frame(frame)
        found_drones = set()
        for ship_id, drones in drone_data:
            self.parse_drones(ship_id, drones, scene_dict, t, found_drones)
        self.update_active_drones(found_drones, scene_dict, t)


def get_scene_name_from_match_json(match_json):
    return "{red} vs {blue}".format(
        red=match_json["redTeam"]["teamName"],
        blue=match_json["blueTeam"]["teamName"]
    )

EXPLOSION_BASE_PATH = "res:/fisfx/deathexplosion/death"

def get_death_explosion_info(radius, raceName):
    """
    This method builds an explosion path using the raceID. If raceName is not
    defined we use rogue drone explosions as a fallback.
    Takes an optional base path as an argument.
    """
    if raceName is None:
        raceName = "rogue"

    if radius < 20.0:
        # drone sized
        size = "_d_"
        delay = 0
        scale = radius / 20.0
    elif radius < 100.0:
        # small
        size = "_s_"
        delay = 100
        scale = radius / 100.0
    elif radius < 400.0:
        # medium
        size = "_m_"
        delay = 250
        scale = radius / 400.0
    elif radius < 1500.0:
        # large
        size = "_l_"
        delay = 500
        scale = radius / 700.0
    elif radius < 6000.0:
        # capital ship (huge)
        size = "_h_"
        delay = 1000
        scale = radius / 6000.0
    else:
        # titan sized
        size = "_t_"
        delay = 2000
        scale = 1.0

    path = EXPLOSION_BASE_PATH + size + raceName + ".red"
    return path, delay, scale


def get_base_url(full_url):
    parse_result = urlparse.urlparse(full_url)
    return "{scheme}://{netloc}".format(scheme=parse_result.scheme, netloc=parse_result.netloc)


def get_scene_dict(target_url):
    scene_dict = {
        "ships": {},
        "projectiles": {},
        "removed_ships": {},
        "drones": {"locations": {}},
        "added_drones": {},
        "removed_drones": {},
    }
    match_json = fetch_json_from_endpoint(requests, target_url)

    scene_dict["scene_name"] =  get_scene_name_from_match_json(match_json)

    staticSceneData = fetch_json_from_endpoint(requests, match_json["staticSceneData"]["href"])
    ships = staticSceneData["ships"]
    scene_dict["nebula_name"] = staticSceneData["nebulaName"]

    for ship in ships:
        ship_url = ship["item"]["href"]
        ship_item_id = get_str_id_from_href(ship_url)
        type_data = fetch_json_from_endpoint(requests, ship["type"]["href"])

        respath = str(type_data["graphicID"]["sofDNA"])
        race = respath.split(":")[-1]
        radius = type_data["radius"]

        scene_dict[ship_item_id] = {}
        scene_dict[ship_item_id]["respath"] = respath
        scene_dict[ship_item_id]["race"] = race

        scene_dict[ship_item_id]["explosion"] = {}
        explosion_path, explosion_delay, explosion_scale = get_death_explosion_info(radius, race)
        scene_dict[ship_item_id]["explosion"]["path"] = explosion_path
        scene_dict[ship_item_id]["explosion"]["delay"] = explosion_delay
        scene_dict[ship_item_id]["explosion"]["scale"] = explosion_scale

        slot = 0
        scene_dict[ship_item_id]["turrets"] = {}
        scene_dict[ship_item_id]["turret_module_id_to_slot"] = {}
        for turret in ship["turrets"]:
            graphic_resource_data = fetch_json_from_endpoint(requests, turret["graphicResource"]["href"])
            respath = graphic_resource_data["graphicFile"]
            module_id = get_str_id_from_href(turret["href"])
            scene_dict[ship_item_id]["turret_module_id_to_slot"][module_id] = slot
            scene_dict[ship_item_id]["turrets"][slot] = respath
            slot += 1

    firstReplayFrame = fetch_json_from_endpoint(requests, match_json["firstReplayFrame"]["href"])
    lastReplayFrame = fetch_json_from_endpoint(requests, match_json["lastReplayFrame"]["href"])
    scene_dict["start_time"] = int(firstReplayFrame["time_str"]) / TIME_UNITS_PER_SECOND
    scene_dict["end_time"] = int(lastReplayFrame["time_str"]) / TIME_UNITS_PER_SECOND
    scene_dict["duration"] = scene_dict["end_time"] - scene_dict["start_time"]

    crest_base_url = get_base_url(target_url)
    frame_parser = FrameParser(crest_base_url, firstReplayFrame, scene_dict)
    frame_parser.parse_frames()
    return scene_dict
