import math

class Vector(object):
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z

    def __add__(self, other):
        return Vector(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other):
        return Vector(self.x - other.x, self.y - other.y, self.z - other.z)

    def __div__(self, scalar):
        return Vector(self.x / scalar, self.y / scalar, self.z / scalar)

    def length_squared(self):
        return self.x ** 2 + self.y ** 2 + self.z ** 2

    def length(self):
        return math.sqrt(self.length_squared())

    def normalize(self):
        my_length = self.length()
        if my_length == 0.0:
            return Vector(1.0, 0.0, 0.0)
        return Vector(
            self.x / my_length,
            self.y / my_length,
            self.z / my_length,
        )

    def to_yaw_pitch_roll(self):
        nv = self.normalize()
        pitch = math.asin(-nv.y)
        yaw = math.atan2(nv.x, nv.z)
        roll = 0
        return yaw, pitch, roll

    def to_list(self):
        return [self.x, self.y, self.z]

    def __repr__(self):
        return "[{x}, {y}, {z}]".format(x=self.x, y=self.y, z=self.z)
