
'''
Script to create a layout:

DFB Laser integrated with Photonic Wire Bonds
Splitter tree using 1x2 splitters
Aggregating submitted designs

by Lukas Chrostowski, Sheri, 2022-25

using SiEPIC-Tools

For more information on scripting:
  https://github.com/SiEPIC/SiEPIC-Tools/wiki/Scripted-Layout
  
usage:
 - run this script, inside KLayout Application, or externally using PyPI package
   - requires siepicfab_ebeam_zep PyPI package 

Install the PDK for develpers:
# cd ... GitHub/SiEPICfab-EBeam-ZEP-PDK
# pip install -e .

 
'''

import siepicfab_ebeam_zep

# Debugging run, or complete
draw_waveguides = True
run_number_designs = 100

# Configuration for the Technology to use
tech = ["SiEPICfab_EBeam_ZEP"]
tech = tech[0]

# Configuration for the arrangement
n_lasers = 3
tree_depth = 4 
die_size = 7800000

waveguide_type={'SiEPICfab_Shuksan_PDK':'Strip TE 1310 nm, w=350 nm', 
                'SiEPICfab_EBeam_ZEP':'Strip TE 1310 nm, w=350 nm (core-clad)'}

blank_design = "design_ZZZ"  # Python design file, otherwise None for terminator.

waveguide_pitch = 8
dy_gcs = 127e3 # pitch of the fiber array
pad_pitch = 250000
metal_width = 20000
metal_width_laser = 50000
metal_width_laser_heater = 20000

# SiEPIC-Tools initialization
import pya
from pya import *
import SiEPIC
from packaging.version import Version
if Version(SiEPIC.__version__) < Version('0.5.14'):
    raise Exception ('This PDK requires SiEPIC-Tools v0.5.14 or greater.')
from SiEPIC import scripts  
from SiEPIC.utils import get_layout_variables
from SiEPIC.scripts import connect_pins_with_waveguide, connect_cell, zoom_out, export_layout
from SiEPIC.utils.layout import new_layout, floorplan
from SiEPIC.utils import get_technology_by_name
from SiEPIC.extend import to_itype

'''
Create a new layout
with a top cell
and Draw the floor plan
'''    
top_cell_name = 'UBC_ELEC413_2025'
cell, ly = new_layout(tech, top_cell_name, GUI=True, overwrite = True)
dbu = ly.dbu

TECHNOLOGY = get_technology_by_name(tech)
if TECHNOLOGY['technology_name'] not in tech or not tech in pya.Technology.technology_names():
    raise Exception ('This example needs to be executed in a layout with Technology = %s' % tech)
else:
    waveguide_type = waveguide_type[tech]

# Floorplan
die_edge = int(die_size/2)
box = Box( Point(-die_edge, -die_edge), Point(die_edge, die_edge) )
cell.shapes(ly.layer(TECHNOLOGY['FloorPlan'])).insert(box)

# load the cells from the PDK
if tech == "SiEPICfab_EBeam_ZEP":
    library = tech
    library_beta = "SiEPICfab_EBeam_ZEP_Beta"
    # library_ubc = "SiEPICfab_EBeam_ZEP_UBC"
    cell_y = ly.create_cell('ybranch_te1310', library)
    #cell_splitter = ly.create_cell('splitter_2x2_1310', library)
    #cell_heater = ly.create_cell('wg_heater', library)
    #cell_waveguide = ly.create_cell('ebeam_pcell_taper',library, {
        #'wg_width1': 0.35,
        #'wg_width2': 0.352})
    cell_waveguide = ly.create_cell('Waveguide_Straight',library_beta, {
        'wg_length': 40,
        'wg_width': 350})
    # cell_waveguide = ly.create_cell('w_straight',library)
    #cell_pad = ly.create_cell('ebeam_BondPad', library)
    cell_gcA = ly.create_cell('GC_Air_te1310_BB', library)
    cell_gcB = ly.create_cell('GC_Air_te1310_BB', library)
    cell_terminator = ly.create_cell('terminator_te1310', library)
    cell_laser = ly.create_cell('laser_1310nm_DFB_BB', library_beta)
    metal_layer = "M1"
    cell_taper = ly.create_cell('ebeam_taper_350nm_2000nm_te1310', library_beta)

if not cell_y:
    raise Exception ('Cannot load 1x2 splitter cell; please check the script carefully.')
#if not cell_splitter:
#    raise Exception ('Cannot load 2x2 splitter cell; please check the script carefully.')
if not cell_taper:
    raise Exception ('Cannot load taper cell; please check the script carefully.')
if not cell_gcA:
    raise Exception ('Cannot load grating coupler cell; please check the script carefully.')
if not cell_gcB:
    raise Exception ('Cannot load grating coupler cell; please check the script carefully.')
if not cell_terminator:
    raise Exception ('Cannot load terminator cell; please check the script carefully.')
if not cell_laser:
    raise Exception ('Cannot load laser cell; please check the script carefully.')
#if not cell_pad:
#    raise Exception ('Cannot load bond pad cell; please check the script carefully.')
if not cell_waveguide:
    raise Exception ('Cannot load Waveguide Straight cell; please check the script carefully.')

# Waveguide type:
waveguides = ly.load_Waveguide_types()
waveguide1 = [w for w in waveguides if w['name']==waveguide_type]
if type(waveguide1) == type([]) and len(waveguide1)>0:
    waveguide = waveguide1[0]
else:
    waveguide = waveguides[0]
    print('error: waveguide type not found in PDK waveguides')
    raise Exception('error: waveguide type (%s) not found in PDK waveguides: \n%s' % (waveguide_type, [w['name'] for w in waveguides]))
radius_um = float(waveguide['radius'])
radius = to_itype(waveguide['radius'],ly.dbu)



# laser_height = cell_laser.bbox().height()
laser_dy = die_size / (n_lasers+1) # spread out evenly
laser_y = -die_size/2 #  


for row in range(0, n_lasers):
    
    # laser, place at absolute position
    laser_x = -die_edge + cell_laser.bbox().top + 150000 + 300e3
    laser_y += laser_dy
    t = pya.Trans.from_s('r0 %s,%s' % (int(laser_x), int(laser_y)) )
    inst_laser = cell.insert(pya.CellInstArray(cell_laser.cell_index(), t))
    
    # splitter tree
    from SiEPIC.utils.layout import y_splitter_tree
    if tree_depth == 4:
        n_x_gc_arrays = 6
        n_y_gc_arrays = 1
        x_tree_offset = 0
        inst_tree_in, inst_tree_out, cell_tree = y_splitter_tree(cell, tree_depth=tree_depth, y_splitter_cell=cell_y, library="SiEPICfab_Shuksan_PDK", wg_type=waveguide_type, draw_waveguides=True)
        ytree_x = inst_laser.bbox().right + x_tree_offset
        ytree_y = inst_laser.pinPoint('opt1').y # - cell_tree.bbox().height()/2
        t = Trans(Trans.R0, ytree_x, ytree_y)
        cell.insert(CellInstArray(cell_tree.cell_index(), t))
    else:
        # Handle other cases if needed
        raise Exception("Invalid tree_depth value")
    
    
    # Waveguide, laser to tree:
    connect_pins_with_waveguide(inst_laser, 'opt1', inst_tree_in, 'opt1', waveguide_type=waveguide_type, turtle_A=[10,90]) #turtle_B=[10,-90, 100, 90])
    
    # Grating couplers
    x_gc_array = -430e3 + x_tree_offset
    x_gc_array = inst_tree_out[0].pinPoint('opt2').x + 100e3
    y_gc_array = ytree_y - 934e3 / 2
       
    n_gcs_eacharray = 8
    dx_gc_arrays = 495e3
    dy_gc_arrays = 950e3+60e3
    dx_gcA_B = 0e3
    dy_gcA_B = 0e3
    
    import numpy as np
    inst_gcA = [[ [0] * n_x_gc_arrays for i in range(n_y_gc_arrays)] for j in range(n_gcs_eacharray) ]
    pointers_designs = []  # location for where the designs should go
    for k in range(0,n_x_gc_arrays):
        for j in range(0,n_y_gc_arrays):
            if k==n_x_gc_arrays-1 and j>1:
                continue
            for i in range(n_gcs_eacharray):
                # Grating couplers:
                t = Trans(Trans.R180, x_gc_array+k*dx_gc_arrays, y_gc_array+i*dy_gcs+j*dy_gc_arrays)
                inst_gcA[i][j][k] = cell.insert(CellInstArray(cell_gcA.cell_index(), t))
                
                if i in [1,2,3,4,5,6]:
                    inst_w = connect_cell(inst_gcA[i][j][k], 'opt1', cell_waveguide, 'opt1', relaxed_pinnames=True)#taper instead of y-branch
                    inst_w.transform(Trans(-10000,0))
                    if k==0 and j==0 and i==1:
                        cell_wg_gc = ly.create_cell('wg_gc')
                        connect_pins_with_waveguide(inst_w, 'opt1', inst_gcA[i][j][k], 'opt1', waveguide_type=waveguide_type, relaxed_pinnames=True).parent_cell=cell_wg_gc
                    cell.insert(CellInstArray(cell_wg_gc.cell_index(), 
                        Trans(Trans.R0, k*dx_gc_arrays,j*dy_gc_arrays+(i-1)*dy_gcs )))                
                if i in [1,3,5]:
                  pointers_designs.append([inst_w])

                #Automated test labels for the devices
                if i in [2,4,6]:
                     l = (i // 2) - 1  
                     t = Trans(Trans.R0, x_gc_array+k*dx_gc_arrays, y_gc_array+i*dy_gcs+j*dy_gc_arrays)
                     text = Text ('opt_in_TE_1310_device_%s_%s_%s' %(l+1,k+1,j+1), t)
                     shape = cell.shapes(ly.layer(TECHNOLOGY['Text'])).insert(text)
                     shape.text_size = 10/ly.dbu
                     shape.text_halign = 2
                
            # Waveguides for loopback:
            if k==0 and j==0:
                cell_wg_loopback = ly.create_cell('wg_loopback')
                #inst_wg_loopbackB = connect_pins_with_waveguide(inst_gcB[0][j][k], 'opt1', inst_gcB[n_gcs_eacharray-1][j][k], 'opt1', waveguide_type=waveguide_type, turtle_A=[10,-90,radius_um*2,-90,60,-90], turtle_B=[10,-90,radius_um*2,-90,60,-90], relaxed_pinnames=True)
                inst_wg_loopbackA = connect_pins_with_waveguide(inst_gcA[0][j][k], 'opt1', inst_gcA[n_gcs_eacharray-1][j][k], 'opt1', waveguide_type=waveguide_type, turtle_A=[10,90,radius_um*2,90,60+dx_gcA_B*ly.dbu+radius_um,90], turtle_B=[10,-90,radius_um*2,-90,60+dx_gcA_B*ly.dbu+radius_um,-90], relaxed_pinnames=True)
                #inst_wg_loopbackB.parent_cell=cell_wg_loopback
                inst_wg_loopbackA.parent_cell=cell_wg_loopback
            inst_wg_loopback = cell.insert(CellInstArray(cell_wg_loopback.cell_index(), 
                Trans(Trans.R0, k*dx_gc_arrays,j*dy_gc_arrays )))
    
            t = Trans(Trans.R0, x_gc_array+k*dx_gc_arrays, y_gc_array+i*dy_gcs+j*dy_gc_arrays)
            # Automated test labels:
            text = Text ('opt_in_TE_1310_device_%s_%s' %(k+1,j+1), t)
            shape = cell.shapes(ly.layer(TECHNOLOGY['Text'])).insert(text)
            shape.text_size = 10/ly.dbu
            shape.text_halign = 2
    
  

# Export for fabrication
import os 
path = os.path.dirname(os.path.realpath(__file__))
filename = os.path.splitext(os.path.basename(__file__))[0]
file_out = export_layout(cell, path, filename, relative_path = '.', format='oas', screenshot=True)


from SiEPIC._globals import Python_Env
if Python_Env == "Script":
    from SiEPIC.utils import klive
    klive.show(file_out, technology=tech)


# print('Completed %s designs' % n_designs)
