bl_info = {
    "name": "Mark Edges (Seam/Sharp)",
    "author": "Sergio ReOl Donate Paypal: sergioreoli@hotmail.com",
    "version": (2, 1),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > Mark Edges",
    "description": "Marca/limpa Seam ou Sharp em bordas de seleção ou arestas/vertices selecionados",
    "category": "Mesh",
}

import bpy
import bmesh

# ===================== PROPRIEDADES DA CENA =====================

def register_props():
    bpy.types.Scene.mark_edges_type = bpy.props.EnumProperty(
        name="Mark Type",
        items=[
            ('SEAM', "Seam", "Marcar como Seam"),
            ('SHARP', "Sharp", "Marcar como Sharp"),
        ],
        default='SEAM'
    )
    bpy.types.Scene.mark_edges_last_count = bpy.props.IntProperty(
        name="Last Count",
        default=0
    )

def unregister_props():
    del bpy.types.Scene.mark_edges_type
    del bpy.types.Scene.mark_edges_last_count


# ===================== OPERADOR APPLY / CLEAR =====================

class MESH_OT_apply_clear_edge_mark(bpy.types.Operator):
    """Aplica ou limpa marcação (Seam/Sharp) nas arestas adequadas"""
    bl_idname = "mesh.apply_clear_edge_mark"
    bl_label = "Apply / Clear Edge Mark"
    bl_options = {'REGISTER', 'UNDO'}

    action: bpy.props.EnumProperty(
        name="Action",
        items=[
            ('APPLY', "Apply", "Aplicar marcação"),
            ('CLEAR', "Clear", "Limpar marcação"),
        ],
        default='APPLY'
    )

    mark_type: bpy.props.EnumProperty(
        name="Mark Type",
        items=[
            ('SEAM', "Seam", "Seam"),
            ('SHARP', "Sharp", "Sharp"),
        ],
        default='SEAM'
    )

    @classmethod
    def poll(cls, context):
        return (context.active_object and
                context.active_object.type == 'MESH' and
                context.mode == 'EDIT_MESH')

    def execute(self, context):
        obj = context.active_object
        mesh = obj.data
        bm = bmesh.from_edit_mesh(mesh)

        # Coletar seleção atual
        faces_selected = [f for f in bm.faces if f.select]
        edges_selected = [e for e in bm.edges if e.select]
        verts_selected = [v for v in bm.verts if v.select]

        target_edges = []

        # 1. Prioridade: faces selecionadas → bordas da seleção
        if faces_selected:
            edge_face_count = {}
            for face in faces_selected:
                for edge in face.edges:
                    edge_face_count[edge] = edge_face_count.get(edge, 0) + 1

            for edge, count in edge_face_count.items():
                total_faces = len(edge.link_faces)
                # É borda se: não tem todas as faces vizinhas selecionadas OU é borda real (total_faces == 1)
                if count < total_faces or total_faces == 1:
                    target_edges.append(edge)

            if not target_edges:
                self.report({'WARNING'}, "Nenhuma aresta de borda encontrada na seleção de faces.")
                return {'CANCELLED'}

        # 2. Se não há faces, usa arestas selecionadas
        elif edges_selected:
            target_edges = edges_selected

        # 3. Se não há faces nem arestas, tenta usar vértices
        elif verts_selected:
            # Pega todas as arestas que conectam os vértices selecionados
            vert_set = set(verts_selected)
            for edge in bm.edges:
                if edge.verts[0] in vert_set and edge.verts[1] in vert_set:
                    target_edges.append(edge)

            if not target_edges:
                self.report({'WARNING'}, "Nenhuma aresta conecta os vértices selecionados.")
                return {'CANCELLED'}

        else:
            self.report({'WARNING'}, "Selecione faces, arestas ou vértices para marcar/limpar.")
            return {'CANCELLED'}

        # Aplicar ou limpar a marcação
        if self.action == 'APPLY':
            if self.mark_type == 'SEAM':
                for e in target_edges:
                    e.seam = True
            else:  # SHARP
                for e in target_edges:
                    e.smooth = False
        else:  # CLEAR
            if self.mark_type == 'SEAM':
                for e in target_edges:
                    e.seam = False
            else:  # SHARP
                for e in target_edges:
                    e.smooth = True

        # Atualizar mesh
        bmesh.update_edit_mesh(mesh)
        mesh.update()

        # Atualizar contagem na cena para mostrar no painel
        context.scene.mark_edges_last_count = len(target_edges)

        self.report({'INFO'}, f"{self.action} {self.mark_type} em {len(target_edges)} arestas.")
        return {'FINISHED'}


# ===================== OPERADOR CLEAR ALL =====================

class MESH_OT_clear_all_marks(bpy.types.Operator):
    """Limpa todas as marcações Seam e Sharp de todas as arestas"""
    bl_idname = "mesh.clear_all_marks"
    bl_label = "Clear All Marks"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.active_object and
                context.active_object.type == 'MESH' and
                context.mode == 'EDIT_MESH')

    def execute(self, context):
        obj = context.active_object
        mesh = obj.data
        bm = bmesh.from_edit_mesh(mesh)

        count = 0
        for e in bm.edges:
            if e.seam or not e.smooth:
                e.seam = False
                e.smooth = True
                count += 1

        bmesh.update_edit_mesh(mesh)
        mesh.update()

        context.scene.mark_edges_last_count = count
        self.report({'INFO'}, f"Limpos {count} arestas (Seam e Sharp removidos).")
        return {'FINISHED'}


# ===================== PAINEL =====================

class VIEW3D_PT_mark_edges_panel(bpy.types.Panel):
    bl_label = "Mark Edges"
    bl_idname = "VIEW3D_PT_mark_edges"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Mark Edges"

    @classmethod
    def poll(cls, context):
        return (context.active_object and
                context.active_object.type == 'MESH' and
                context.mode == 'EDIT_MESH')

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # Dropdown para tipo de marca
        layout.prop(scene, "mark_edges_type", text="Type")

        # Botões Apply e Clear
        row = layout.row(align=True)
        op = row.operator("mesh.apply_clear_edge_mark", text="Apply")
        op.action = 'APPLY'
        op.mark_type = scene.mark_edges_type

        op = row.operator("mesh.apply_clear_edge_mark", text="Clear")
        op.action = 'CLEAR'
        op.mark_type = scene.mark_edges_type

        layout.separator()

        # Botão Clear All
        layout.operator("mesh.clear_all_marks", text="Clear All Marks", icon='X')

        layout.separator()

        # Mostrar último resultado
        if scene.mark_edges_last_count > 0:
            layout.label(text=f"Last operation: {scene.mark_edges_last_count} edges", icon='INFO')
        else:
            layout.label(text="No edges affected yet", icon='INFO')

        layout.separator()
        layout.label(text="Tips:", icon='INFO')
        layout.label(text="• Select faces → marks boundary edges")
        layout.label(text="• Select edges → marks selected edges")
        layout.label(text="• Select vertices → marks edges between them")


# ===================== REGISTRO =====================

classes = (
    MESH_OT_apply_clear_edge_mark,
    MESH_OT_clear_all_marks,
    VIEW3D_PT_mark_edges_panel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    register_props()

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    unregister_props()

if __name__ == "__main__":
    register()
