import geometry
import templates


class EveSpaceScene():
    def __init__(self):
        self.curve_sets = []
    def __str__(self):
        s = templates.eve_space_scene
        if self.curve_sets:
            s += "\ncurveSets:"
        for i in self.curve_sets:
            s += str(i)
        return s


class Tr2ScalarKey(object):
    def __init__(self, time, value, left_tangent, right_tangent):
        self.time = time
        self.value = value
        self.left_tangent = left_tangent
        self.right_tangent = right_tangent

    def __str__(self):
        return templates.scalar_key.format(
            time=self.time,
            value=self.value,
            left_tangent=self.left_tangent,
            right_tangent=self.right_tangent,
            )


class Tr2ScalarCurve(object):
    def __init__(self, curve_type, time_offset, length, start_value, end_value, start_tangent, end_tangent):
        self.curve_type = curve_type
        self.time_offset = time_offset
        self.length = length
        self.start_value = start_value
        self.end_value = end_value
        self.start_tangent = start_tangent
        self.end_tangent = end_tangent
        self.scalar_keys = []

    def __str__(self):
        s = templates.rotation_curve_header.format(
            curve_type=self.curve_type,
            length=self.length,
            start_value=self.start_value,
            end_value=self.end_value,
            start_tangent=self.start_tangent,
            end_tangent=self.end_tangent,
            time_offset=self.time_offset,
            )
        if self.scalar_keys:
            s += "\n            keys:"
        for i in self.scalar_keys:
            s += str(i)

        return s



class Tr2EulerRotation(object):
    def __init__(self, object_name, yaw, pitch, roll):
        self.object_name = object_name
        self.yaw = yaw
        self.pitch = pitch
        self.roll = roll

    def __str__(self):
        s = templates.euler_rotation_header.format(
            object_name=self.object_name
        )
        if self.yaw is not None:
            s += self.yaw.__str__()
        if self.pitch is not None:
            s += self.pitch.__str__()
        if self.roll is not None:
            s += self.roll.__str__()
        return s


class Tr2VectorKey(object):
    def __init__(self, object_name, value, right_tangent, left_tangent, time):
        self.object_name = object_name
        self.value = value
        self.right_tangent = right_tangent
        self.left_tangent = left_tangent
        self.time = time


    def __str__(self):
        return templates.vector_key.format(
            object_name=self.object_name,
            value=self.value,
            right_tangent=self.right_tangent,
            left_tangent=self.left_tangent,
            time=self.time
            )


class Tr2VectorCurve(object):
    def __init__(self, object_name, time_offset, length, start_value, end_value, start_tangent, end_tangent):
        self.object_name = object_name
        self.time_offset = time_offset
        self.length = length
        self.start_value = start_value
        self.end_value = end_value
        self.start_tangent = start_tangent
        self.end_tangent = end_tangent
        self.keys = []

    def __str__(self):
        s = templates.location_curve_header.format(
            object_name=self.object_name,
            time_offset=self.time_offset,
            length=self.length,
            start_value=self.start_value,
            end_value=self.end_value,
            start_tangent=self.start_tangent,
            end_tangent=self.end_tangent,
        )
        if self.keys:
            s += "\n        keys:"
            for i in self.keys:
                s += str(i)
        return s


class TriCurveSet(object):
    def __init__(self, object_name):
        self.object_name = object_name
        self.curves = []

    def __str__(self):
        s = templates.curve_set_header.format(object_name=self.object_name)
        for c in self.curves:
            s += c.__str__()
        return s

    def __repr__(self):
        return """TriCurveSet
        {
            {object_name}
            {curves}
        }
        """.format(
            object_name = self.object_name,
            curves = self.curves
        )


class RedFile(object):
    def __init__(self):
        self.scene = EveSpaceScene()
        self.curve_sets = {}

    def add_vector_curve(self, id, time_offset, length, start_value, end_value):
        start_tangent = [0.0, 0.0, 0.0]
        end_tangent = [0.0, 0.0, 0.0]
        if id not in self.curve_sets:
            curve_set = TriCurveSet(id)
            self.curve_sets[id] = curve_set
        else:
            curve_set = self.curve_sets[id]
        curve_set.curves.append(Tr2VectorCurve(id, time_offset, length, start_value, end_value, start_tangent, end_tangent))
        self.scene.curve_sets.append(curve_set)

    def add_vector_key(self, id, value, time):
        curve_set = self.curve_sets[id]
        vector_curve = None
        for curve in curve_set.curves:
            if isinstance(curve, Tr2VectorCurve):
                vector_curve = curve
                break
        left_tangent = [0, 0, 0]
        right_tangent = [0, 0, 0]
        key = Tr2VectorKey(id, value, right_tangent, left_tangent, time)
        vector_curve.keys.append(key)

    def add_rotation_curve(self, id, time_offset, length, start_value, end_value):
        start_tangent = [0.0, 0.0, 0.0]
        end_tangent = [0.0, 0.0, 0.0]
        if id not in self.curve_sets:
            curve_set = TriCurveSet(id)
            self.curve_sets[id] = curve_set
        else:
            curve_set = self.curve_sets[id]

        start_yaw, start_pitch, start_roll = start_value.to_yaw_pitch_roll()
        end_yaw, end_pitch, end_roll = end_value.to_yaw_pitch_roll()

        yaw_curve =   Tr2ScalarCurve("yawCurve",   time_offset, length, start_yaw, end_yaw, 0.0, 0.0)
        pitch_curve = Tr2ScalarCurve("pitchCurve", time_offset, length, start_pitch, end_pitch, 0.0, 0.0)
        roll_curve =  Tr2ScalarCurve("rollCurve",  time_offset, length, start_roll, end_roll, 0.0, 0.0)

        curve_set.curves.append(Tr2EulerRotation(id, yaw_curve, pitch_curve, roll_curve))
        self.scene.curve_sets.append(curve_set)

    def add_rotation_key(self, id, value, time):
        curve_set = self.curve_sets[id]
        euler_curve = None
        for curve in curve_set.curves:
            if isinstance(curve, Tr2EulerRotation):
                euler_curve = curve
                break
        left_tangent = 0.0
        right_tangent = 0.0

        yaw_value, pitch_value, roll_value = value.to_yaw_pitch_roll()

        yaw_key = Tr2ScalarKey(time, yaw_value, right_tangent, left_tangent)
        pitch_key = Tr2ScalarKey(time, pitch_value, right_tangent, left_tangent)
        roll_key = Tr2ScalarKey(time, roll_value, right_tangent, left_tangent)
        euler_curve.yaw.scalar_keys.append(yaw_key)
        euler_curve.pitch.scalar_keys.append(pitch_key)
        euler_curve.roll.scalar_keys.append(roll_key)

    def save(self, file_path):
        with open(file_path, "w") as f:
            f.write(self.scene.__str__())

    def display(self):
        print self.scene
