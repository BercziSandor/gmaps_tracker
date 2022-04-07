import hs as hs
from geographiclib.geodesic import Geodesic
from locationsharinglib import Person
# import haversine as hs
import geographiclib


def get_location(person: Person):
    return {'loc': (person.latitude, person.longitude), 'accuracy': person.accuracy}


DIRECTION_NAMES_EN = ["north", "north east", "east", "south east", "south", "south west", "west",
                      "north west"]
DIRECTION_NAMES_HU = ["É", "ÉK", "K", "DK", "D", "DNY", "NY",
                      "ÉNY"]

DIRECTION_NAMES_HU_16 = ["É", "ÉÉK", "ÉK", "KÉK", "K", "KDK", "DK", "DDK", "D", "DDNY", "DNY", "NYDNY", "NY", "NYÉNY",
                         "ÉNY", "NYÉNY"]


# https://stackoverflow.com/questions/47659249/calculate-cardinal-direction-from-gps-coordinates-in-python


def get_distance_p(person_1: Person, person_2: Person):
    return get_distance(get_location(person_1), get_location(person_2))


def get_distance(location_1, location_2):
    dist = hs.haversine(location_1.get('loc', (0.0, 0.0)), location_2.get('loc', (0.0, 0.0)), unit=Unit.METERS)

    pm = location_1.get('accuracy', 0) + location_2.get('accuracy', 0)
    return {'distance_m': dist,
            'plusminus_m': pm}


def meter_to_human(meters: float = 0):
    retval = ""
    if meters < 0.0:
        retval = "ERROR: distance can't be negative"
    elif meters < 20:
        retval = "{:.1f} m".format(meters)
    elif meters < 2000:
        retval = "{} m".format(round(meters))
    elif meters < 20000:
        retval = "{} km".format(round(meters / 1000.0, 1))
    else:
        retval = "{} km".format(int(round(meters / 1000.0, 0)))
    return retval


def persons_dist_info(person1: Person, person2: Person):
    g = Geodesic.WGS84.Inverse(person1.latitude, person1.longitude, person2.latitude, person2.longitude)
    distance_meters = g['s12']
    bearing = g['azi1']


    # https://en.wikipedia.org/wiki/Points_of_the_compass#32_cardinal_points
    # 0:   N
    # 90:  E
    # 180: S
    # 270: W
    pm = person1.accuracy + person2.accuracy

    print(
        f"Distance from you and {person2.nickname}: {int(distance_meters)}±{pm}m, direction: {int(bearing)}° ({get_bearing_name(bearing)})")


a = meter_to_human(1.499)
a = meter_to_human(14.499)
a = meter_to_human(114.499)
a = meter_to_human(1114.499)
a = meter_to_human(11114.499)
a = meter_to_human(111114.499)
