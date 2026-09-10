# Mesh / TF Troubleshooting

Use this when the robot looks correct in MuJoCo but wrong in Foxglove, RViz, or another ROS visualizer.

## 1. Separate kinematics from mesh rendering

A robot can have:

- correct joint states
- correct TF frames
- incorrect-looking meshes

Move one joint at a time and temporarily inspect only the TF frames in Foxglove.

If the correct child frames move about the correct joints, the kinematic chain is probably fine.

## 2. Look for a systematic mesh rotation

If **all meshes are rotated in a similar way**, especially with a plane swap such as:

```text
expected: XZ plane
shown:    XY plane
```

suspect a mesh coordinate/up-axis convention before changing the URDF.

## 3. Foxglove fix for YAM STL meshes

In the Foxglove 3D panel:

```text
Settings
-> Scene
-> Mesh up axis
-> Z
```

Refresh the panel if needed.

This changes only how Foxglove interprets the STL geometry. It does **not** change:

- ROS TF
- joint axes
- joint states
- the URDF
- MuJoCo physics

Hopefully, this fixes your problem.

## 4. Quick diagnosis

```text
TF wrong
    -> check joint origin, axis, hierarchy, or joint states

TF correct + one mesh wrong
    -> check that link's <visual><origin> or mesh file

TF correct + all meshes wrong similarly
    -> check viewer mesh/up-axis settings
```

## 5. Before editing the robot description

Compare the same robot in two renderers.

If MuJoCo or RViz looks correct but Foxglove does not, first check visualization/import settings rather than modifying joint or visual transforms.
