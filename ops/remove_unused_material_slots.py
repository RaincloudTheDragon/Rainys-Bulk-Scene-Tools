"""Remove unused material slots from editable local meshes (#19)."""

import bpy


def _is_editable_local_mesh(obj) -> bool:
    """True for local meshes that are safe for material_slot_remove_unused."""
    if obj is None or obj.type != "MESH":
        return False
    if not obj.material_slots:
        return False
    # Linked data and library overrides fail the built-in op poll.
    if obj.library is not None:
        return False
    if getattr(obj, "override_library", None) is not None:
        return False
    data = getattr(obj, "data", None)
    if data is not None and (
        data.library is not None or getattr(data, "override_library", None) is not None
    ):
        return False
    return True


class RemoveUnusedMaterialSlots(bpy.types.Operator):
    """Remove unused material slots from all editable local mesh objects"""

    bl_idname = "bst.remove_unused_material_slots"
    bl_label = "Remove Unused Material Slots"
    bl_description = (
        "Remove unused material slots from local mesh objects "
        "(skips linked and library-override meshes)"
    )
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        processed = 0
        skipped = 0

        original_active = context.view_layer.objects.active
        original_selection = list(context.selected_objects)

        try:
            for obj in bpy.data.objects:
                if not _is_editable_local_mesh(obj):
                    if (
                        obj.type == "MESH"
                        and obj.material_slots
                        and (
                            obj.library is not None
                            or getattr(obj, "override_library", None) is not None
                        )
                    ):
                        skipped += 1
                    continue

                was_linked = False
                if obj.name not in context.view_layer.objects:
                    try:
                        context.scene.collection.objects.link(obj)
                        was_linked = True
                    except Exception:
                        skipped += 1
                        continue

                original_obj_selection = obj.select_get()
                try:
                    obj.select_set(True)
                    context.view_layer.objects.active = obj

                    # Guard: override/poll/context failures must not abort the batch.
                    with context.temp_override(
                        active_object=obj,
                        object=obj,
                        selected_objects=[obj],
                        selected_editable_objects=[obj],
                    ):
                        if not bpy.ops.object.material_slot_remove_unused.poll():
                            skipped += 1
                            continue
                        bpy.ops.object.material_slot_remove_unused()
                    processed += 1
                except Exception:
                    skipped += 1
                finally:
                    try:
                        obj.select_set(original_obj_selection)
                    except Exception:
                        pass
                    if was_linked:
                        try:
                            context.scene.collection.objects.unlink(obj)
                        except Exception:
                            pass
        finally:
            context.view_layer.objects.active = original_active
            for sel in list(context.selected_objects):
                sel.select_set(False)
            for obj in original_selection:
                if obj.name in context.view_layer.objects:
                    obj.select_set(True)

        if skipped:
            self.report(
                {"INFO"},
                f"Cleared unused slots on {processed} mesh(es); "
                f"skipped {skipped} linked/override/unavailable",
            )
        else:
            self.report(
                {"INFO"},
                f"Removed unused material slots from {processed} mesh objects",
            )
        return {"FINISHED"}
