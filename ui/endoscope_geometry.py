"""
In here you'll find the maths behind the simulated endoscope view.
The scene (units: canal radius R = 1):
  - The ear canal is a cylinder of radius 1 along the z axis
    (x = right, y = DOWN, z = forward, towards the eardrum).
  - The eardrum is a plane at depth DRUM_DEPTH, tilted by DRUM_TILT_DEG
    (lower part further away), textured with the image.
  - The robot's camera sits at the canal entrance, at z = 0.

The camera pose comes from the joysticks, all normalized -1..1:
  - translation (tx, ty): sideways shift of the camera inside the canal,
    up to MAX_SHIFT canal radii — gives parallax;
  - orientation (yaw, pitch): where the camera points, up to
    MAX_ANGLE_DEG — tilts the view.

Screen coordinates returned here are "normalized": (x/z, y/z) in camera
space. CameraView multiplies them by its focal length in pixels.

DISCLAIMER: Once again measures were chosen deliberately by me, but are not
exactly accurate, we should choose smt more anatomically correct maybe.
"""

import math

DRUM_DEPTH = 2.3            # eardrum distance from camera, in canal radii
DRUM_TILT_DEG = 15.0        # eardrum tilt around the x axis
DRUM_HALF_SIZE = 1.15       # half-width of the eardrum image 
WALL_Z_START = 0.15         # nearest wall ring (right at the camera) --> i.e. where visible canal starts
WALL_RINGS = 22             # wall detail along the canal...
WALL_SEGMENTS = 48          # ... and around it. More = smoother but slower to draw
MAX_SHIFT = 0.5             # max shifting of camera sideways
MAX_ANGLE_DEG = 16.0        # max camera yaw / pitch
HALF_FOV_TAN = 0.60         # endoscope FOV, about 62°
_NEAR = 0.05                # points closer than this to the camera are ignored


def _clamp(v, lo=-1.0, hi=1.0):
    return max(lo, min(hi, v))


class Pose:
    def __init__(self, tx=0.0, ty=0.0, yaw=0.0, pitch=0.0):
        self.tx, self.ty = _clamp(tx), _clamp(ty)
        self.yaw, self.pitch = _clamp(yaw), _clamp(pitch)

    def camera(self):
        #(position, right, down, forward) vectors in world space. turns the joystick values --> real cam
        pos = (self.tx * MAX_SHIFT, self.ty * MAX_SHIFT, 0.0)
        a = math.radians(MAX_ANGLE_DEG)#forward direction
        fx, fy, fz = math.tan(self.yaw * a), math.tan(self.pitch * a), 1.0
        n = math.sqrt(fx * fx + fy * fy + fz * fz)
        fwd = (fx / n, fy / n, fz / n)
        rn = math.hypot(fwd[2], fwd[0]) #rx direction
        right = (fwd[2] / rn, 0.0, -fwd[0] / rn)
        #down directin: at 90° to both, using cross product
        down = (fwd[1] * right[2] - fwd[2] * right[1],
                fwd[2] * right[0] - fwd[0] * right[2],
                fwd[0] * right[1] - fwd[1] * right[0])
        return pos, right, down, fwd


def _dot(a, b): # dot product to see how much a vector points in the direction of b
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _to_camera(p, cam):# describes p as seen from camera, how far right how far lx, down/up, and in front od it
    pos, right, down, fwd = cam
    d = (p[0] - pos[0], p[1] - pos[1], p[2] - pos[2])
    return _dot(d, right), _dot(d, down), _dot(d, fwd)


def _project(p, cam): #defines where a 3d point appears on screen
    x, y, z = _to_camera(p, cam)
    if z <= _NEAR:
        return None, z
    return (x / z, y / z), z
# dividiamo per la distanza so that far things = smaller + closer to centre. inoltre ritorna none for pts behind camera


def _drum_point(u, v):
    # Point on the tilted eardrum plane; u, v in -1..1 (v = 1 = bottom edge)
    t = math.radians(DRUM_TILT_DEG)
    s = DRUM_HALF_SIZE
    #moving down the image (v>0) also moves the pt further away because of the tilt
    return (u * s, v * s * math.cos(t), DRUM_DEPTH + v * s * math.sin(t))


def drum_corners(pose):
    # 4 corners of the eardrum image appear on screen . CameraView stretches image to fit them
    # which makes the eardrum look tilted when turning the camera. Otherwise return none when corner is behind it
    cam = pose.camera()
    out = []
    for u, v in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        pt, _z = _project(_drum_point(u, v), cam)
        if pt is None:
            return None
        out.append(pt)
    return out


def wall_quads(pose):
    #splits the canal into small patches and works out for each one of them the respective 4 corners on screen
    # + how bright it should be from 0 to1. the pathces come back sorted from far to near (slide on painter's algorithm,
    # still to be finished but the analogy gives the idea --> maybe study smt else to explain it better).
    cam = pose.camera()
    t = math.radians(DRUM_TILT_DEG)
    z_end = DRUM_DEPTH - DRUM_HALF_SIZE * math.sin(t) * 0.3 #wall stops before eardrum
    #rings along the canal --> **1.6 li mette piu vicini alla cam dove il wall looks biggest on screen e ha bisogno di + detail
    zs = [WALL_Z_START + (z_end - WALL_Z_START) * (i / WALL_RINGS) ** 1.6
          for i in range(WALL_RINGS + 1)]
    angles = [2 * math.pi * k / WALL_SEGMENTS for k in range(WALL_SEGMENTS + 1)]
    quads = []
    for i in range(WALL_RINGS):
        z0, z1 = zs[i], zs[i + 1]
        for k in range(WALL_SEGMENTS):
            a0, a1 = angles[k], angles[k + 1]
            #i 4 angoli del patch sono sulla superficie del cilindro (cos a, sin a, z). project each one
            # e keep track della distanza
            pts, depth = [], 0.0
            for z, a in ((z0, a0), (z0, a1), (z1, a1), (z1, a0)):
                pt, zc = _project((math.cos(a), math.sin(a), z), cam)
                if pt is None:
                    break
                pts.append(pt)
                depth += zc
                #skippa tutti i patches che sono parzialmente behind cam
            if len(pts) < 4:
                continue
            depth /= 4
            # Light comes from the scope closer = brighter; a
            # little extra light from above for shape.
            light = min(1.0, (0.9 / max(depth, 0.9)) ** 0.9)
            light *= 0.88 + 0.12 * (-math.sin((a0 + a1) / 2))
            #never fully dark --> brightness always inbetween 0.25 e 1
            quads.append((pts, max(0.25, min(1.0, light)), depth, i))
    quads.sort(key=lambda q: -q[2])
    return [(q[0], q[1], q[3]) for q in quads]


def drum_brightness(): #eardrum has a fixed brightness, a bit dimmer than the closest wall, pero idk if it's the best choise
# maybe it's not that realistic like this idk, but the 3d structures in the image lilke the ossicles are actually not
#3d and flat so idk would be a nightmare to create shadows based on them --> to re-evaluate everything once maybe
# another image is used to make it more high-fid. to the real ear canal 
    return 0.82


def aim_uv(pose):
   #finds where the cross hits the eardrum
    pos, _right, _down, fwd = pose.camera()
    t = math.radians(DRUM_TILT_DEG)
    # The eardrum surface: its centre o, its two directions across the
    # image (ex = right, ey = down the tilted surface) and the
    # direction n that sticks straight out of it.
    ex = (1.0, 0.0, 0.0)
    ey = (0.0, math.cos(t), math.sin(t))
    n = (0.0, -math.sin(t), math.cos(t))
    denom = _dot(fwd, n)# se la cam è almost // to eardrum the LOS (line of sight --> cross) never hits it
    if abs(denom) < 1e-6:
        return None
    o = (0.0, 0.0, DRUM_DEPTH)#neg value = eardrum behind cam
    s = _dot((o[0] - pos[0], o[1] - pos[1], o[2] - pos[2]), n) / denom
    if s <= 0:
        return None
    hit = (pos[0] + fwd[0] * s, pos[1] + fwd[1] * s, pos[2] + fwd[2] * s)
    rel = (hit[0] - o[0], hit[1] - o[1], hit[2] - o[2])
    u = _dot(rel, ex) / DRUM_HALF_SIZE
    v = _dot(rel, ey) / DRUM_HALF_SIZE
    return 0.5 + u * 0.5, 0.5 + v * 0.5
