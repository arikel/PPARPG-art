""" 
    EGG exporter for Blender 2.57.1 
    rev 7
"""
FILE_PATH = './test.egg' #: file name to write
# { 'animation_name' : (start_frame, end_frame, frame_rate) }
ANIMATIONS = {'anim1':(0,10,5), 
              }

import bpy, os
from mathutils import *
from math import pi

class Group:
    """
    Representation of the EGG <Group> hierarchy structure as the
    linked list "one to many".
    """
    def __init__(self, obj):
        self.object = obj #: Link to the blender's object
        self.childs = []  #: List of children (Groups)
    
    def make_hierarchy_from_list(self, obj_list):
        """ This function make <Group> hierarchy from the list of
        Blender's objects. Self.object is the top level of the created 
        hierarchy. Usually in this case self.object == None
        
        @param obj_list: tuple or lis of blender's objects.
        """
        for obj in obj_list:
            if ((obj.parent == self.object) or 
                ((self.object == None) and 
                 (str(obj.parent) not in map(str,obj_list)) and 
                 (str(obj) not in [str(ch.object) for ch in self.childs]))):
                gr = self.__class__(obj)
                self.childs.append(gr)
                gr.make_hierarchy_from_list(obj_list)
                
    def print_hierarchy(self, level = 0):
        """ Debug function to print out hierarchy to console.
        
        @param level: starting indent level.
        """
        print('-' * level, self.object)
        for ch in self.childs:
            ch.print_hierarchy(level+1)
            
    def get_tags_egg_str(self, level = 0):
        """ Create and return <Tag> string from Blender's object 
        Game logic properties.
        
        @param level: indent level.
        
        @return: the EGG tags string.
        """
        egg_str = ''
        if self.object:
            for prop in self.object.game.properties:
                egg_str += '%s<Tag> %s { %s }\n' % ('  ' * level, 
                                                    eggSafeName(prop.name),
                                                    eggSafeName(prop.value))
        return egg_str
                
            
    def get_full_egg_str(self,level = 0):
        """ Create and return representation of the EGG  <Group>  
        with hierarchy, started from self.object. It's start point to
        generating EGG structure.
        
        @param level: starting indent level.
        
        @return: full EGG string of group.
        """
        egg_str = ''
        if self.object:
            egg_str += '%s<Group> %s {\n' % ('  ' * level, eggSafeName(self.object.name))
            egg_str += self.get_tags_egg_str(level + 1)
            if self.object.type == 'MESH':
                if (('ARMATURE' in [m.type for m in self.object.modifiers]) or 
                    (((self.object.data.shape_keys) and 
                      (len(self.object.data.shape_keys.key_blocks) > 1)))):
                    egg_str += '%s<Dart> { 1 }\n' % ('  ' * (level + 1))
                    egg_mesh = EGGActorObjectData(self.object)
                else:
                    egg_mesh = EGGMeshObjectData(self.object)
                for line in egg_mesh.get_full_egg_str().splitlines():
                    egg_str += '%s%s\n' % ('  ' * (level + 1), line)
            elif self.object.type == 'CURVE':
                egg_obj = EGGNurbsCurveObjectData(self.object)
                for line in egg_obj.get_full_egg_str().splitlines():
                    egg_str += '%s%s\n' % ('  ' * (level + 1), line)
            elif self.object.type != 'ARMATURE':
                egg_obj = EGGBaseObjectData(self.object)
                for line in egg_obj.get_full_egg_str().splitlines():
                    egg_str += '%s%s\n' % ('  ' * (level + 1), line)
            for ch in self.childs:
                egg_str += ch.get_full_egg_str(level + 1)
            egg_str += '%s}\n' % ('  ' * level)
        else:        
            for ch in self.childs:
                egg_str += ch.get_full_egg_str(level + 1)
        return egg_str
                    

class EGGArmature(Group):
    """ Representation of the EGG <Joint> hierarchy. Recive Blender's 
    bones list as obj_list in constructor.
    """
    
    def get_full_egg_str(self, vrefs, tr_matrix, level = 0):
        """ Create and return string representation of the EGG <Joint> 
        with hieratchy.
        
        @param vrefs: reference of vertices, linked to bones.
        @param tr_matrix: matrix_world taken from Armature object, 
        becouse bone objects hasn't matrix_world.
        @param level: indent level.
        
        @return: the EGG string with joints hierarchy
        """
        egg_str = ''
        if self.object:
            egg_str += '%s<Joint> %s {\n' % ('  ' * level, eggSafeName(self.object.name))
            # Get vertices reference by Bone name from globlal armature vref
            if self.object.name in list(vrefs.keys()):
                vref = vrefs[self.object.name]
            else:
                vref = {}
            joint = EGGJointObjectData(self.object, vref, tr_matrix)
            for line in joint.get_full_egg_str().splitlines():
                egg_str += '%s%s\n' % ('  ' * (level + 1), line)
            for ch in self.childs:
                egg_str += ch.get_full_egg_str(vrefs, tr_matrix, level + 1)
            egg_str += '%s}\n' % ('  ' * level)
        else:
            for ch in self.childs:
                egg_str += ch.get_full_egg_str(vrefs, tr_matrix, level + 1)
        return egg_str


#-----------------------------------------------------------------------
#                           BASE OBJECT                                 
#-----------------------------------------------------------------------
class EGGBaseObjectData:
    """ Base representation of the EGG objects  data
    """
    
    def __init__(self, obj):
        self.obj_ref = obj
        self.transform_matrix = obj.matrix_world
        
    def get_transform_str(self):
        """ Return the EGG string representation of object transforms.
        """
        tr_str = '<Transform> {\n  <Matrix4> {\n'
        for i in range(4):
            #tr_str += '    ' + ' '.join(map(str, self.transform_matrix[i])) + '\n'
            m = self.transform_matrix[i]
            tr_str += '    %.6f %.6f %.6f %.6f\n' % (m[0], m[1], m[2], m[3])
        tr_str += '  }\n}\n'        
        return tr_str
        
    def get_full_egg_str(self):
        return self.get_transform_str() + '\n'
        

class EGGNurbsCurveObjectData(EGGBaseObjectData):
    """ Representation of the EGG NURBS Curve
    """
    def collect_vertices(self):
        str6f = lambda x: '%.6f' % x
        vertices = []
        idx = 0
        for spline in self.obj_ref.data.splines:
            for vtx in spline.points:
                co = vtx.co * self.obj_ref.matrix_world
                vertices.append('<Vertex> %i {\n  %s\n}\n' % (idx, 
                                    ' '.join(map(str6f, co))))
                idx += 1
        return vertices
                
        
    def get_vtx_pool_str(self):
        """ Return the vertex pool string in the EGG syntax. 
        """
        vtx_pool = ''
        vertices = self.collect_vertices()
        if vertices:
            vtx_pool = '<VertexPool> %s {\n' % eggSafeName(self.obj_ref.name)
            for vtx_str in vertices:
                for line in vtx_str.splitlines():
                    vtx_pool += '  ' + line + '\n'
            vtx_pool += '}\n'
        return vtx_pool
        
    def get_curves_str(self):
        """ Return the <NURBSCurve> string. Blender 2.5 has not contain
        Knots information, seems it's calculating in runtime. 
        I got algorythm for the knots calculation from the OBJ exporter
        and modified it.
        """
        str2f = lambda x: '%.2f' % x
        cur_str = ''
        idx = 0
        for spline in self.obj_ref.data.splines:
            if spline.type == 'NURBS':
                knots_num = spline.point_count_u + spline.order_u
                knots = [i/(knots_num - 1) for i in range(knots_num)]
                if spline.use_endpoint_u:
                    for i in range(spline.order_u - 1):
                        knots[i] = 0.0
                        knots[-(i + 1)] = 1.0
                    for i in range(knots_num - (spline.order_u * 2) + 2):
                        knots[i + spline.order_u - 1] = i/(knots_num - (spline.order_u * 2) + 1)
                cur_str += '<NURBSCurve> {\n'
                cur_str += '  <Scalar> subdiv { %i }\n' % (spline.resolution_u * \
                                                    (spline.point_count_u - 1))
                cur_str += '  <Order> { %i }\n' % spline.order_u
                cur_str += '  <Knots> { %s }\n' % ' '.join(map(str2f, knots))
                cur_str += '  <VertexRef> {\n    %s\n    <Ref> { %s } \n  }\n' % ( 
                        ' '.join([str(i) for i in range(idx, idx + \
                        spline.point_count_u)]), eggSafeName(self.obj_ref.name))
                cur_str += '}\n'
                idx += spline.point_count_u
        return cur_str
        
    def get_full_egg_str(self):
        return self.get_transform_str() + self.get_vtx_pool_str() + self.get_curves_str()
        

class EGGJointObjectData(EGGBaseObjectData):
    """ Representation of the EGG <Joint> data
    """
    
    def __init__(self, obj, vref, matrix):
        """ @param vref: reference of vertices, linked to bone.
        @param matrix: matrix_world taken from Armature object, 
        becouse bone objects hasn't matrix_world.
        """
        self.obj_ref = obj
        if not obj.parent:
            self.transform_matrix = matrix * obj.matrix_local
        else:
            self.transform_matrix = obj.parent.matrix_local.inverted() * obj.matrix_local
        self.vref = vref
        
    def get_vref_str(self):
        """ Convert vertex reference to the EGG string and return it.
        """
        vref_str = ''
        for vpool, data in self.vref.items():
            weightgroups = {}
            for idx, weight in data:
                wstr = '%.6f' % weight
                if wstr not in list(weightgroups.keys()):
                    weightgroups[wstr] = []
                weightgroups[wstr].append(idx)
            for wgrp, idxs in weightgroups.items():
                vref_str += '<VertexRef> {\n'
                vref_str += '  ' + ' '.join(map(str,idxs)) + '\n'
                vref_str += '  <Scalar> membership { %s }' % wgrp
                vref_str += '  <Ref> { %s }\n}\n' % vpool
        return vref_str
    
    def get_full_egg_str(self):
        return self.get_transform_str() + '\n' + self.get_vref_str()
        
        
#-----------------------------------------------------------------------
#                           MESH OBJECT                                 
#-----------------------------------------------------------------------
class EGGMeshObjectData(EGGBaseObjectData):
    """ EGG data representation of the mesh object
    """

    def __init__(self, obj):
        EGGBaseObjectData.__init__(self, obj)
        self.smooth_vtx_list = self.get_smooth_vtx_list()
        self.poly_vtx_ref = self.pre_convert_poly_vtx_ref()
        self.uvs_list = self.pre_convert_uvs()


    #-------------------------------------------------------------------
    #                           AUXILIARY                               

    def get_smooth_vtx_list(self):
        """ Collect the smoothed polygon vertices 
        for write normals of the vertices. In the EGG for the smooth 
        shading used normals of vertices. For solid - polygons.
        """
        vtx_list = []
        for f in self.obj_ref.data.faces:
            if f.use_smooth:
                for v in f.vertices:                
                    vtx_list.append(v)
        return set(vtx_list)
        
    def pre_convert_uvs(self):
        """ Blender uses shared vertices, but for the correct working 
        UV and shading in the Panda needs to convert they are in the 
        individual vertices for each polygon.
        """
        uv_list = []
        for uv_layer in self.obj_ref.data.uv_textures:
            data = []
            for uv_face in uv_layer.data:
                for u,v in uv_face.uv:
                    data.append((u,v))
            uv_list.append((uv_layer.name, data))
        return uv_list
        
    def pre_convert_poly_vtx_ref(self):
        """ Blender uses shared vertices, but for the correct working 
        UV and shading in the Panda needs to convert they are in the 
        individual vertices for each polygon.
        """
        poly_vtx_ref = []
        idx = 0
        for face in self.obj_ref.data.faces:
            vtxs = []
            for v in face.vertices:
                vtxs.append(idx)
                idx += 1
            poly_vtx_ref.append(vtxs)
        return poly_vtx_ref
        
    
    #-------------------------------------------------------------------
    #                           VERTICES                                

    def collect_vtx_xyz(self, vidx, attributes):
        """ Add coordinates of the vertex to the vertex attriibutes list
        
        @param vidx: Blender's internal vertex index.
        @param attributes: list of vertex attributes
        
        @return: list of vertex attributes.
        """
        co = self.obj_ref.data.vertices[vidx].co * self.obj_ref.matrix_world
        co = map(str, co)
        attributes.append(' '.join(co))
        return attributes
        
    def collect_vtx_dxyz(self, vidx, attributes):
        """ Add morph target <Dxyz> to the vertex attributes list.
        
        @param vidx: Blender's internal vertex index.
        @param attributes: list of vertex attributes
        
        @return: list of vertex attributes.
        """
        if ((self.obj_ref.data.shape_keys) and (len(self.obj_ref.data.shape_keys.key_blocks) > 1)):
            for i in range(1,len(self.obj_ref.data.shape_keys.key_blocks)):
                key = self.obj_ref.data.shape_keys.key_blocks[i]
                vtx = self.obj_ref.data.vertices[vidx]
                co = key.data[vidx].co * self.obj_ref.matrix_world - \
                     vtx.co * self.obj_ref.matrix_world
                if co.length > 0.000001:
                    attributes.append('<Dxyz> "%s" { %.6f %.6f %.6f }\n' % \
                                      (key.name, co[0], co[1], co[2]))
        return attributes
        
    def collect_vtx_normal(self, vidx, attributes):
        """ Add <Normal> to the vertex attributes list.
        
        @param vidx: Blender's internal vertex index.
        @param attributes: list of vertex attributes
        
        @return: list of vertex attributes.
        """
        if vidx in self.smooth_vtx_list:
            no = self.obj_ref.data.vertices[vidx].normal * self.obj_ref.matrix_world.to_euler().to_matrix()
            attributes.append('<Normal> { %.6f %.6f %.6f }' % (no[0], no[1], no[2]))
        return attributes
        
    def collect_vtx_rgba(self, vidx, attributes):
        return attributes
        
    def collect_vtx_uv(self, ividx, attributes):
        """ Add <UV> to the vertex attributes list.
        
        @param vidx: the EGG (converted) vertex index.
        @param attributes: list of vertex attributes
        
        @return: list of vertex attributes.
        """
        for name, data in self.uvs_list:
            try:
                attributes.append('<UV> %s { %.6f %.6f }' % (name, data[ividx][0], data[ividx][1]))
            except:
                print('ERROR: can\'t get UV information in "collect_vtx_uv"')
        return attributes
        
    def collect_vertices(self):
        """ Convert and collect vertices info. 
        """
        vertices = []
        idx = 0
        for f in self.obj_ref.data.faces:
            for v in f.vertices:
                # v - Blender inner vertex index
                # idx - Vertex index for the EGG
                vtx = '<Vertex> %s {\n' % idx
                attributes = []
                self.collect_vtx_xyz(v, attributes)
                self.collect_vtx_dxyz(v, attributes)
                self.collect_vtx_normal(v, attributes)
                self.collect_vtx_rgba(v, attributes)
                self.collect_vtx_uv(idx, attributes)
                for attr in attributes:
                    for attr_str in attr.splitlines():
                        vtx += '  ' + attr_str + '\n'
                vtx += '}\n'
                vertices.append(vtx)
                idx += 1
        return vertices
    
    #-------------------------------------------------------------------
    #                           POLYGONS                                
    
    def collect_poly_tref(self, face, attributes):
        """ Add <TRef> to the polygon's attributes list.
        
        @param face: face index.
        @param attributes: list of polygon's attributes.
        
        @return: list of polygon's attributes.
        """
        for uv_tex in self.obj_ref.data.uv_textures:
            if uv_tex.data[face.index].use_image:
                if uv_tex.data[face.index].image.source == 'FILE':
                    attributes.append('<TRef> { %s }' % uv_tex.data[face.index].image.name)
        if face.material_index < len(bpy.data.materials):
            mat = bpy.data.materials[face.material_index]
            for tex in [tex for tex in mat.texture_slots if tex]:
                if ((tex.texture_coords == 'UV') and (not tex.texture.use_nodes)):
                    if tex.texture.image.source == 'FILE':
                        attributes.append('<TRef> { %s }' % tex.texture.name)
        return attributes
    
    def collect_poly_mref(self, face, attributes):
        """ Add <MRef> to the polygon's attributes list.
        
        @param face: face index.
        @param attributes: list of polygon's attributes.
        
        @return: list of polygon's attributes.
        """
        if face.material_index < len(bpy.data.materials):
            mat = bpy.data.materials[face.material_index]
            attributes.append('<MRef> { %s }' % mat.name)
        return attributes
    
    def collect_poly_normal(self, face, attributes):
        """ Add <Normal> to the polygon's attributes list.
        
        @param face: face index.
        @param attributes: list of polygon's attributes.
        
        @return: list of polygon's attributes.
        """
        no = face.normal * self.obj_ref.matrix_world.to_euler().to_matrix()
        attributes.append('<Normal> {%.6f %.6f %.6f}' % (no[0], no[1], no[2]))
        return attributes
    
    def collect_poly_rgba(self, face, attributes):
        return attributes
    
    def collect_poly_bface(self, face, attributes):
        """ Add <BFace> to the polygon's attributes list.
        
        @param face: face index.
        @param attributes: list of polygon's attributes.
        
        @return: list of polygon's attributes.
        """
        if [uv_face.data[face.index] for uv_face in self.obj_ref.data.uv_textures if uv_face.data[face.index].use_twoside]:
            attributes.append('<BFace> { 1 }')
        return attributes
        
    def collect_poly_vertexref(self, face, attributes):
        """ Add <VertexRef> to the polygon's attributes list.
        
        @param face: face index.
        @param attributes: list of polygon's attributes.
        
        @return: list of polygon's attributes.
        """
        vr = ' '.join(map(str,self.poly_vtx_ref[face.index]))
        attributes.append('<VertexRef> { %s <Ref> { %s }}' % (vr, self.obj_ref.name))
        return attributes
    
    def collect_polygons(self):
        """ Convert and collect polygons info 
        """
        polygons = []
        for f in self.obj_ref.data.faces:
            poly = '<Polygon> {\n'
            attributes = []
            self.collect_poly_tref(f, attributes)
            self.collect_poly_mref(f, attributes)
            self.collect_poly_normal(f, attributes)
            self.collect_poly_rgba(f, attributes)
            self.collect_poly_bface(f, attributes)
            self.collect_poly_vertexref(f, attributes)
            for attr in attributes:
                for attr_str in attr.splitlines():
                    poly += '  ' + attr_str + '\n'
            poly += '}\n'
            polygons.append(poly)
        return polygons
        
    def get_vtx_pool_str(self):
        """ Return the vertex pool string in the EGG syntax. 
        """
        vtx_pool = '<VertexPool> %s {\n' % self.obj_ref.name
        for vtx_str in self.collect_vertices():
            for line in vtx_str.splitlines():
                vtx_pool += '  ' + line + '\n'
        vtx_pool += '}\n'
        return vtx_pool
        
    def get_polygons_str(self):
        """ Return polygons string in the EGG syntax 
        """
        polygons = '\n'
        for poly_str in self.collect_polygons():
            for line in poly_str.splitlines():
                polygons += line + '\n'
        return polygons
        
    def get_full_egg_str(self):
        """ Return full mesh data representation in the EGG string syntax 
        """
        return self.get_transform_str() + '\n' \
                + self.get_vtx_pool_str() + '\n' \
                + self.get_polygons_str()


#-----------------------------------------------------------------------
#                           ACTOR OBJECT                                
#-----------------------------------------------------------------------
class EGGActorObjectData(EGGMeshObjectData):
    """ Representation of the EGG animated object data
    """
    
    def __init__(self, obj):
        EGGMeshObjectData.__init__(self,obj)
        self.joint_vtx_ref = self.pre_convert_joint_vtx_ref()
        
    def pre_convert_joint_vtx_ref(self):
        """ Collect and convert vertices, assigned to the bones
        """
        joint_vref = {}
        idx = 0
        for face in self.obj_ref.data.faces:
            for v in face.vertices:
                for g in self.obj_ref.data.vertices[v].groups:
                    gname = self.obj_ref.vertex_groups[g.group].name
                    # Goup name = Joint (bone) name
                    if gname not in list(joint_vref.keys()):
                        joint_vref[gname] = {}
                    # Object name = vertices pool name
                    if self.obj_ref.name not in list(joint_vref[gname].keys()):
                        joint_vref[gname][self.obj_ref.name] = []
                    joint_vref[gname][self.obj_ref.name].append((idx, g.weight))
                idx += 1
        return joint_vref
        
    def get_joints_str(self):
        """ Make  the EGGArmature object from the bones, pass the 
        vertex referense to it, and return the EGG string representation 
        of the joints hierarchy.
        """
        j_str = ''
        for mod in self.obj_ref.modifiers:
            if mod.type == 'ARMATURE':
                ar = EGGArmature(None)
                ar.make_hierarchy_from_list(mod.object.data.bones)
                j_str += ar.get_full_egg_str(self.joint_vtx_ref, mod.object.matrix_world, -1)
        return j_str
        
    def get_full_egg_str(self):
        """ Return string representation of the EGG animated object data.
        """
        return self.get_vtx_pool_str() + '\n' \
                + self.get_polygons_str() + '\n' \
                + self.get_joints_str() + '\n'


#-----------------------------------------------------------------------
#                     SCENE MATERIALS & TEXTURES                        
#-----------------------------------------------------------------------
def get_used_materials():
    """ Collect Materials used in the selected object. 
    """
    m_list = []
    for obj in bpy.context.selected_objects:
        if obj.type == 'MESH':
            for f in obj.data.faces:
                if f.material_index < len(bpy.data.materials):
                    m_list.append(f.material_index)
    return set(m_list)


def get_used_textures():
    """ Collect images from the UV images and Material texture slots 
    """
    tex_list = {}
    for obj in bpy.context.selected_objects:
        if obj.type == 'MESH':
            for uv in obj.data.uv_textures:
                for f in uv.data:
                    if f.use_image:
                        if f.image.source == 'FILE':
                            if not f.image.name in tex_list:
                                tex_list[f.image.name] = (uv.name, bpy.path.relpath(f.image.filepath))

            for f in obj.data.faces:
                if f.material_index < len(bpy.data.materials):
                    for tex in bpy.data.materials[f.material_index].texture_slots:
                        if ((tex) and (not tex.texture.use_nodes)):
                            if tex.texture_coords == 'UV':
                                if tex.uv_layer:
                                    uv_name = tex.uv_layer
                                else:
                                    uv_name = obj.data.uv_textures[0].name
                                if tex.texture.image.source == 'FILE':
                                    if not tex.texture.name in list(tex_list.keys()):
                                        try:
                                            tex_list[tex.texture.name] = \
                                            (uv_name, bpy.path.relpath(tex.texture.image.filepath))
                                        except:
                                            print('ERROR: can\'t get texture image on %s.' % tex.texture.name)
    return tex_list

def get_egg_materials_str():
    """ Return the EGG string of used materials
    """
    mat_str = ''
    for m_idx in get_used_materials():
        mat = bpy.data.materials[m_idx]
        mat_str += '<Material> %s {\n' % mat.name
        mat_str += '  <Scalar> diffr { %.6f }\n' % (mat.diffuse_color[0] * mat.diffuse_intensity)
        mat_str += '  <Scalar> diffg { %.6f }\n' % (mat.diffuse_color[1] * mat.diffuse_intensity)
        mat_str += '  <Scalar> diffb { %.6f }\n' % (mat.diffuse_color[2] * mat.diffuse_intensity)
        mat_str += '  <Scalar> specr { %.6f }\n' % (mat.specular_color[0] * mat.specular_intensity)
        mat_str += '  <Scalar> specg { %.6f }\n' % (mat.specular_color[1] * mat.specular_intensity)
        mat_str += '  <Scalar> specb { %.6f }\n' % (mat.specular_color[2] * mat.specular_intensity)
        mat_str += '  <Scalar> shininess { %.6f }\n' % (mat.specular_hardness / 512 * 128)
        mat_str += '  <Scalar> emitr { %.6f }\n' % (mat.emit * 0.1)
        mat_str += '  <Scalar> emitg { %.6f }\n' % (mat.emit * 0.1)
        mat_str += '  <Scalar> emitb { %.6f }\n' % (mat.emit * 0.1)
        #file.write('  <Scalar> ambr { %.6f }\n' % (mat.ambient))
        #file.write('  <Scalar> ambg { %.6f }\n' % (mat.ambient))
        #file.write('  <Scalar> ambb { %.6f }\n' % (mat.ambient))
        mat_str += '}\n\n'
    for name, path in get_used_textures().items():
        mat_str += '<Texture> %s {\n' % name
        mat_str += '  "' + convertFileNameToPanda(path[1]) + '"\n'
        mat_str += '  <Scalar> uv-name { %s }\n' % path[0]
        mat_str += '}\n\n'
    return mat_str

class EGGAnimJoint(Group):
    """ Representation of the <Joint> animation data. Has the same 
    hierarchy as the character's skeleton.
    """
    
    def get_full_egg_str(self, anim_info, framerate, level = 0):
        """ Create and return the string representation of the <Joint>
        animation data, included all joints hierarchy.
        """
        egg_str = ''
        if self.object:
            egg_str += '%s<Table> %s {\n' % ('  ' * level, eggSafeName(self.object.name))
            bone_data = anim_info['<skeleton>'][self.object.name]
            egg_str += '%s  <Xfm$Anim> xform {\n' % ('  ' * level)
            egg_str += '%s    <Scalar> order { sphrt }\n' % ('  ' * level)
            egg_str += '%s    <Scalar> fps { %i }\n' % ('  ' * level, framerate)
            egg_str += '%s    <Scalar> contents { ijkprhxyz }\n' % ('  ' * level)
            egg_str += '%s    <V> {\n' % ('  ' * level)
            for i in range(len(bone_data['r'])):
                egg_str += '%s      %.6f %.6f %.6f %.6f %.6f %.6f %.6f %.6f %.6f\n' % (
                                                    '  ' * level, 1.0, 1.0, 1.0, 
                                                    bone_data['p'][i], 
                                                    bone_data['r'][i], 
                                                    bone_data['h'][i],
                                                    bone_data['x'][i], 
                                                    bone_data['y'][i], 
                                                    bone_data['z'][i])
            egg_str += '%s    }\n' % ('  ' * level)
            egg_str += '%s  }\n' % ('  ' * level)
            for ch in self.childs:
                egg_str += ch.get_full_egg_str(anim_info, framerate, level + 1)
            egg_str += '%s}\n' % ('  ' * level)
        else:        
            for ch in self.childs:
                egg_str += ch.get_full_egg_str(anim_info, framerate, level + 1)
        return egg_str

class AnimCollector():
    """ Collect an armature and a shapekeys animation data and 
    convert it to the EGG string.
    """
    
    def __init__(self, obj_list, start_f, stop_f, framerate, name):
        """ @param obj_list: list or tuple of the Blender's objects
        for wich needed to collect animation data.
        @param start_f: number of the "from" frame.
        @param stop_f: number of the "to" frame.
        @param framerate: framerate for the given animation.
        @param name: name of the animation for access in the Panda.
        """
        self.obj_list = obj_list
        self.start_f = start_f
        self.stop_f = stop_f
        self.framerate = framerate
        self.name = name
        self.bone_groups = {}
        for arm in bpy.data.armatures:
            arm.pose_position = 'POSE'
        self.obj_anim_ref = {}
        for obj in obj_list:
            if obj.type == 'MESH':
                for mod in obj.modifiers:
                    if mod:
                        if mod.type == 'ARMATURE':
                            self.bone_groups[obj.name] = EGGAnimJoint(None)
                            self.bone_groups[obj.name].make_hierarchy_from_list(mod.object.data.bones)
                            if obj.name not in list(self.obj_anim_ref.keys()):
                                self.obj_anim_ref[obj.name] = {}
                            self.obj_anim_ref[obj.name]['<skeleton>'] = \
                                    self.collect_arm_anims(mod.object)
                if ((obj.data.shape_keys) and (len(obj.data.shape_keys.key_blocks) > 1)):
                    if obj.name not in list(self.obj_anim_ref.keys()):
                        self.obj_anim_ref[obj.name] = {}
                    self.obj_anim_ref[obj.name]['morph'] = self.collect_morph_anims(obj)
    
    def collect_morph_anims(self, obj):
        """ Collect an animation data for the morph target (shapekeys).
        
        @param obj: Blender's object for wich need to collect an animation data
        """
        keys = {}
        if ((obj.data.shape_keys) and (len(obj.data.shape_keys.key_blocks) > 1)):
            current_f = bpy.context.scene.frame_current
            anim_dict = {}
            for f in range(self.start_f, self.stop_f):
                bpy.context.scene.frame_current = f
                bpy.context.scene.frame_set(f)
                for i in range(1,len(obj.data.shape_keys.key_blocks)):
                    key = obj.data.shape_keys.key_blocks[i]
                    if key.name not in list(keys.keys()):
                        keys[key.name] = []
                    keys[key.name].append(key.value)
            bpy.context.scene.frame_current = current_f
        return keys
    
    def collect_arm_anims(self, arm):
        """ Collect an animation data for the skeleton (Armature).
        
        @param arm: Blender's Armature for wich need to collect an animation data
        """
        current_f = bpy.context.scene.frame_current
        anim_dict = {}
        for f in range(self.start_f, self.stop_f):
            bpy.context.scene.frame_current = f
            bpy.context.scene.frame_set(f)
            for bone in arm.pose.bones:
                if bone.name not in list(anim_dict.keys()):
                    anim_dict[bone.name] = {}
                for k in 'ijkabcrphxyz':
                    if k not in list(anim_dict[bone.name].keys()):
                        anim_dict[bone.name][k] = []
                if bone.parent:
                    matrix = bone.parent.matrix.inverted() * bone.matrix
                else:
                    matrix = arm.matrix_world * bone.matrix

                p, r, h = matrix.to_euler()
                anim_dict[bone.name]['p'].append(p/pi*180)
                anim_dict[bone.name]['r'].append(r/pi*180)
                anim_dict[bone.name]['h'].append(h/pi*180)
                x, y, z = matrix.to_translation()
                anim_dict[bone.name]['x'].append(x)
                anim_dict[bone.name]['y'].append(y)
                anim_dict[bone.name]['z'].append(z)
        bpy.context.scene.frame_current = current_f
        return anim_dict
    
    def get_morph_anim_str(self, obj_name):
        """ Create and return the EGG string of the morph animation for
        the given object.
        
        @param obj_name: name of the Blender's object
        """
        morph_str = ''
        data = self.obj_anim_ref[obj_name]
        if 'morph' in list(data.keys()):
            str4f = lambda x: '%.4f' % x
            morph_str += '<Table> morph {\n'
            for key, anim_vals in data['morph'].items():
                morph_str += '  <S$Anim> %s {\n' % eggSafeName(key)
                morph_str += '    <Scalar> fps { %i }\n' % self.framerate
                morph_str += '    <V> { %s }\n' % (' '.join(map(str4f, anim_vals)))
                morph_str += '  }\n'
            morph_str += '}\n'
        return morph_str

    def get_skeleton_anim_str(self, obj_name):
        """ Create and return the EGG string of the Armature animation for
        the given object.
        
        @param obj_name: name of the Blender's object
        """
        skel_str = ''
        data = self.obj_anim_ref[obj_name]
        if '<skeleton>' in list(data.keys()):
            skel_str += '<Table> "<skeleton>" {\n'
            for line in self.bone_groups[obj_name].get_full_egg_str(data, self.framerate, -1).splitlines():
                skel_str += '  %s\n' % line
            skel_str += '}\n'
        return skel_str
              
    def get_full_egg_str(self):
        """ Create and return the full EGG string for the animation, wich
        has been setup in the object constructor (__init__)
        """
        egg_str = ''
        if self.obj_anim_ref:
            egg_str += '<Table> {\n'
            for obj_name, obj_data in self.obj_anim_ref.items():
                if self.name:
                    anim_name = self.name
                else:
                    anim_name = obj_name
                egg_str += '  <Bundle> %s {\n' % eggSafeName(anim_name)
                for line in self.get_skeleton_anim_str(obj_name).splitlines():
                    egg_str += '    %s\n' % line
                for line in self.get_morph_anim_str(obj_name).splitlines():
                    egg_str += '    %s\n' % line
                egg_str += '  }\n'
            egg_str += '}\n'
        return egg_str

def eggSafeName(s):
  """ (Get from Chicken) Function that converts names into something 
  suitable for the egg file format - simply puts " around names that 
  contain spaces and prunes bad characters, replacing them with an 
  underscore.
  """
  s = str(s).replace('"','_') # Sure there are more bad characters, but this will do for now.
  if ' ' in s:
    return '"' + s + '"'
  else:
    return s

def convertFileNameToPanda(filename):
  """ (Get from Chicken) Converts Blender filenames to Panda 3D filenames.
  """
  path =  filename.replace('//', './').replace('\\', '/')
  if os.name == 'nt' and path.find(':') != -1:
    path = '/'+ path[0].lower() + path[2:]
  return path

#-----------------------------------------------------------------------
#                           WRITE OUT                                   
#-----------------------------------------------------------------------
def write_out():
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode='OBJECT')
    gr = Group(None)
    gr.make_hierarchy_from_list(bpy.context.selected_objects)
    #gr.print_hierarchy()
    file = open(FILE_PATH, 'w')
    file.write('<CoordinateSystem> { Z-up } \n')
    file.write(get_egg_materials_str())
    file.write(gr.get_full_egg_str())
    for a_name, frames in ANIMATIONS.items():
        ac = AnimCollector(bpy.context.selected_objects, 
                            frames[0], 
                            frames[1], 
                            frames[2], 
                            a_name)
        file.write(ac.get_full_egg_str())
    file.close()

write_out()

