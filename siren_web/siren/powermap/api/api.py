import math
from powermap.logic.grid import dust

class PowermapAPI:
    def __init__(self, config, settings):
        self.settings = settings
        self.config= config

    def find_shortest(self, coords1, coords2):
        shortest = [99999, -1., -1., -1, -1]
        for i in range(len(coords2) - 1):
            dist = dust(coords1[0], coords1[1], coords2[i][0], coords2[i][1], coords2[i + 1][0], coords2[i + 1][1])
            if dist[0] >= 0 and dist[0] < shortest[0]:
                shortest = dist[:]
                shortest.append(i)
        return shortest

    def destinationxy(self, lon1, lat1, bearing, distance):
        radius = 6367  # Earth's radius in km
        ln1, lt1, baring = list(map(math.radians, [lon1, lat1, bearing]))
        lat2 = math.asin(math.sin(lt1) * math.cos(distance / radius) +
                         math.cos(lt1) * math.sin(distance / radius) * math.cos(baring))
        lon2 = ln1 + math.atan2(math.sin(baring) * math.sin(distance / radius) * math.cos(lt1),
                                math.cos(distance / radius) - math.sin(lt1) * math.sin(lat2))
        return math.degrees(lat2), math.degrees(lon2)
