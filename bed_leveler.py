import serial
import time
import numpy as np
import sys

# Configure the serial port parameters
# Replace 'COM4' with your port name (e.g., '/dev/ttyUSB0' on Linux or 'COMx' on Windows)
# Ensure the baud rate matches the device you are communicating with (e.g., Arduino)

# Define ANSI color codes as constants
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    RESET = '\033[0m' # Resets the color/style


ser = serial.Serial(
    port='/dev/cu.usbmodem1101', 
    baudrate=115200, 
    bytesize=serial.EIGHTBITS, 
    parity=serial.PARITY_NONE, 
    stopbits=serial.STOPBITS_ONE, 
    timeout=1 # Timeout in seconds for read operations
)

"""
while (True):
    line = ser.readline().decode('utf-8').strip()
    print(f"Data received: {line}")
    send = input("SEND:\n") + "\n"
    if send == "quit\n":
        break
    else:
        ser.write(send.encode("utf-8"))

"""


###
###
###     MAKE SURE TO PROBE THE COPPER CLAD BOARD IN 
###     THE BANTAM SOFTWARE AT X=0, Y=0
###     (delete this text if that doesn't work)
###


def get_z_from_triangle(x1, y1, z1, x2, y2, z2, x3, y3, z3, x, y):
    """
    Returns the Z value where the point (x, y) intersects the plane
    defined by the triangle (x1,y1,z1), (x2,y2,z2), (x3,y3,z3).
    """

    # Edge vectors
    e1 = np.array([x2 - x1, y2 - y1, z2 - z1])
    e2 = np.array([x3 - x1, y3 - y1, z3 - z1])

    # Plane normal
    A, B, C = np.cross(e1, e2)

    # Plane constant
    D = -(A * x1 + B * y1 + C * z1)

    if abs(C) < 1e-12:
        raise ValueError("Triangle plane is vertical; cannot solve for z.")

    # Solve plane equation for z
    z = -(A * x + B * y + D) / C
    return z


def home_bantam():
    ser.write(b'G28.2 Z0 X0 Y0\n')

def initializeBantam():
    print(f"Opening serial port: {ser.name}")
    time.sleep(2) # Wait for the connection to establish

    # Write data: convert string to bytes before writing
    ser.write(b'{ej:1}\n')
    ser.write(b'{sr:{posx:t, posy:t, posz:t, mpox:t, mpoy:t, mpoz:t, plan:t, vel:t, unit:t, stat:t, dist:t, admo:t, frmo:t, coor:t}}{"r":{"ej":1},"f":[1,0,8]}\n')
    ser.write(b'{jv:4}\n')
    ser.write(b'{qv:0}\n')
    ser.write(b'{sv:1}\n')
    ser.write(b'$$\n')
    ser.write(b'{mfoe:1}\n')
    ser.write(b'{mtoe:1}\n')
    ser.write(b'{ssoe:1}\n')
    ser.write(b'{xam:1, yam:1, zam:1}\n')
    ser.write(b'{sr:n}\n')
    ser.write(b'{si:200}\n')
    home_bantam()
    print("HOMING X,Y,Z")
    line = 'sonething'

    while (line != ''):
        line = ser.readline().decode('utf-8').strip()
        #print(f"Data received: {line}")

def find_bed():
    ser.write(b'M05 G94 G90 G21 G64 G17 G55 F0S0 (starting sandbox)\n')
    ser.write(b'{"prbr":t}\n')
    ser.write(b'{"prbin":5}\n')
    ser.write(b'G54\n')
    ser.write(b'G90 (absolute position)\n')
    ser.write(b'G38.3Z-60.5F50\n')
    ser.write(b'M05 G94 G90 G21 G64 G17 G55 F0S0 (exiting sandbox)\n')
    ser.write(b'm100\n')

def receive_until_get(what_you_receive):
    is_receiving = True
    while (is_receiving):
        line = ser.readline().decode('utf-8').strip()
        if line[0:len(what_you_receive)] == what_you_receive:
            break
        #print(f"Data received: {line}")
    return line

def get_z_coord():
    ser.write(b'g91 g0 z1\n')
    time.sleep(1)
    find_bed()
    probe_string = receive_until_get('{"prb"')  # Receive Data until the probe hits the bed
    ser.write(b'g90 g0 z5')
    z_coord_string = probe_string[probe_string.find('"z":')+4:probe_string.find(',"a"')]
    return float(z_coord_string)

def find_vertices(lod_x, lod_y, coord_x_list, coord_y_list, adjust_grid, x, y):
    #    1_____3                      3
    #    |    /                      /| 
    #    |   /          OR          / |
    #    |  /                      /  |
    #    | /                      /   |
    #    2                       2____1
    #   
    #    i     i+1               i    i+1

    vertex1 = [0, 0, 0]
    vertex2 = [0, 0, 0]
    vertex3 = [0, 0, 0]

    for i in range(lod_x-1):
        if (coord_x_list[i] <= x) and (coord_x_list[i+1] > x):
            vertex3[0] = coord_x_list[i+1]
            vertex2[0] = coord_x_list[i]
            
            for j in range(lod_y-1):
                if (coord_y_list[j] <= y) and (coord_y_list[j+1] > y):
                    vertex3[1] = coord_y_list[j+1]
                    vertex2[1] = coord_y_list[j]
                    slope = (vertex3[1]-vertex2[1])/(vertex3[0]-vertex2[0])
                    y_intercept = vertex2[1]-slope*vertex2[0]

                    if (slope*x + y_intercept) >= y:
                        vertex1[0] = vertex3[0]
                        vertex1[1] = vertex2[1]
                        vertex1[2] = adjust_grid[i+1][j]
                    if (slope*x + y_intercept) < y:
                        vertex1[0] = vertex2[0]
                        vertex1[1] = vertex3[1]
                        vertex1[2] = adjust_grid[i][j+1]
                    vertex3[2] = adjust_grid[i+1][j+1]
                    vertex2[2] = adjust_grid[i][j]
    
    return vertex1, vertex2, vertex3



##
## Get PCB dimensions from Gcode
##
x_range = [99999, -99999]    # [x_min, x_max]
y_range = [99999, -99999]    # [y_min, y_max]

doesFileExist = False
gcode_file_str = ""

while (not doesFileExist):
    try:
        print("\nMake sure the gcode only moves within the cuts, and doesn't move to X0Y0 unnecessarily")
        gcode_file_str = input("What is the name of the file containing your GCode? (include filename extension)\n")

        with open(gcode_file_str, 'r') as gcode_file:
            for line in gcode_file:   
                x_index = line.find("X")
                y_index = line.find("Y")
                if x_index != -1 and y_index != -1:
                    current_x = float(line[x_index+1:y_index])
                    current_y = float(line[y_index+1:line.find("\n")])

                    if (current_x < x_range[0]):
                        x_range[0] = current_x
                    elif (current_x > x_range[1]):
                        x_range[1] = current_x
                    if (current_y < y_range[0]):
                        y_range[0] = current_y
                    elif (current_y > y_range[1]):
                        y_range[1] = current_y
        doesFileExist = True
    except FileNotFoundError as e:
        print("That file doesn't exist.\n")

if (x_range[0] == 99999) or (x_range[1] == -99999) or (y_range[0] == 99999) or (y_range[1] == -99999):
    print("Gcode autoranger failed")
    raise ValueError("Gcode autoranger failed")



print("PCB X Range: ", x_range)
print("PCB Y Range: ", y_range)








pcb_width = x_range[1] - x_range[0]+2
print("PCB Width: ", pcb_width)
pcb_height = y_range[1] - y_range[0]+2
print("PCB Height: ", pcb_height)
pcb_offset_x = x_range[0] - 1
pcb_offset_y = y_range[0] - 1
print("PCB Offset X:", pcb_offset_x, "Y:", pcb_offset_y)

detail_x = int(input("What PCB width resolution would you like (2,4,8)?\n"))
detail_y = int(input("What PCB height resolution would you like (2,4,8)?\n"))

# Creates a 3x4 list filled with zeros
grid = [[0 for _ in range(detail_y)] for _ in range(detail_x)]
adjusted_grid = grid

coord_grid_x = [0 for _ in range(detail_x)]
coord_grid_y = [0 for _ in range(detail_y)]

# Generate an array that holds all of the coordinates for the bed level probes
for i in range(detail_y):
    for j in range(detail_x):
        coord_grid_x[j] = (pcb_width*j/(detail_x-1)) + pcb_offset_x
        coord_grid_y[i] = (pcb_height*i/(detail_y-1)) + pcb_offset_y

# grid will be like [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]

# Setup and home
try:
    initializeBantam()
except Exception as e:
    print(f"\n\n{Colors.RED}It looks like the Bantam isn't connecting to the python code.")
    print("• Make sure no other programs are trying to connect over Serial (e.g. Bantam, UGS).")
    print("• Make sure the location of the correct port is written in python code (default: /dev/cu.usbmodem1201).")
    print(f"• Make sure the CNC is turned on.\n{Colors.RESET}")
    sys.exit()

# Read data: read a line up to a newline character
# The read data is in bytes and needs to be decoded


# Go to z=10
ser.write(b'G90 G0 Z5\n')
# Go to bottom left corner
ser.write(b'G90 G0 X0Y0\n')

print("\nMeasuring Points\n")

for i in range(detail_y):
    for j in range(detail_x):
        ser.write(b'G90 G0 Z5\n') # Move up vertically
        xy_coord_string = "G90 G0 " + 'X'+str(coord_grid_x[j]) +'Y'+str(coord_grid_y[i]) + "\n"
        ser.write(xy_coord_string.encode('utf-8'))
        z_coord = get_z_coord()
        grid[j][i] = z_coord
        
print("This is the coord grid for x: \n", coord_grid_x)
print("This is the coord grid for y: \n", coord_grid_y)
print("This is the grid: ", grid)

origin_height = grid[0][0]

for i in range(detail_y):
    for j in range(detail_x):
        adjusted_grid[j][i] = round(grid[j][i] - origin_height, 5)

print("This is the adjusted grid: ", adjusted_grid)
ser.write(b'G90 G0 Z10\n')
# Go to bottom left corner
ser.write(b'G90 G0 X0Y0\n')


time.sleep(1)
ser.close()




##
##  Adjust the GCode File
##


print("This is the adjusted grid: \n")
x_range = list(range(detail_x))
y_range = list(range(detail_y))



for y in y_range[::-1]:
    for x in x_range:
        print(str(adjusted_grid[x][y]) + " | ", end="")
    print("\n") 


some_x = 1
some_y = 29

does_file_exist = False
                
try: 
    print("\n")

    current_x = 0
    current_y = 0
    current_z = 0
    last_known_z = 0
    delta_z = 0



    with open(gcode_file_str, 'r') as gcode_file, open(gcode_file_str[0:len(gcode_file_str)-3]+"_adjusted.nc", 'w') as gcode_file_adj:
        for line in gcode_file:
            
            # Insantiate the vertices
            v1 = [0, 0, 0]
            v2 = v1
            v3 = v1

            # find the index of the letter Z in the line
            z_index = line.find("Z")

            # If there is a z, get the coordinate to the right of it
            if z_index != -1:
                last_known_z = float(line[z_index+1:line.find("\n")])
                gcode_file_adj.write(line.rstrip())
                gcode_file_adj.write("Z"+str(last_known_z))
            else:
                gcode_file_adj.write(line.rstrip())
            
            x_index = line.find("X")
            y_index = line.find("Y")
            if x_index != -1 and y_index != -1:
                current_x = float(line[x_index+1:y_index])
                current_y = float(line[y_index+1:line.find("\n")])
                
                # Find the values of the vertices based on the current Position
                v1, v2, v3 = find_vertices(detail_x, detail_y, coord_grid_x, coord_grid_y, adjusted_grid, current_x, current_y)

                # Get the diffence of Z relative to the origin
                delta_z = get_z_from_triangle(v1[0], v1[1], v1[2], v2[0], v2[1], v2[2], v3[0], v3[1], v3[2], current_x, current_y)
                current_z = last_known_z + delta_z
                gcode_file_adj.write(" Z"+str(round(current_z, 4)))
            
            gcode_file_adj.write("\n")
                

        
        does_file_exist = True
except Exception as e:
    # Handle any other potential exceptions that might occur
    print(f"An unexpected error occurred: {e}")


print("After completing the bed leveling, you MUST probe the bed and set the PCB height at X="+str(coord_grid_x[0])+" Y="+str(coord_grid_y[0]))

gcode_file.close()