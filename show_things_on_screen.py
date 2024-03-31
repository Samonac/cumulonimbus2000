import tkinter as tk


# Define some colors
RED = "#FF0000"
GREEN = "#00FF00"
BLUE = "#0000FF"
YELLOW = "#FFFF00"
WHITE = "#FFFFFF"
square_size = 50
window_size = 500

class TransparentCanvas(tk.Canvas):
    def __init__(self, master=None, **kwargs):
        tk.Canvas.__init__(self, master, **kwargs)
        self.shape_alpha = 1.0  # Initial alpha value for shapes
        self.shape_ids = []  # Store shape ids

    def set_shape_alpha(self, value):
        self.shape_alpha = float(value) / 100  # Convert slider value to alpha value
        self.redraw_shapes()

    def draw_rectangle(self, *args, **kwargs):
        kwargs['fill'] = self.adjust_alpha(kwargs.get('fill', ''), self.shape_alpha)
        shape_id = self.create_rectangle(*args, **kwargs)
        self.shape_ids.append(shape_id)  # Store shape id
        return shape_id

    def draw_oval(self, *args, **kwargs):
        kwargs['fill'] = self.adjust_alpha(kwargs.get('fill', ''), self.shape_alpha)
        shape_id = self.create_oval(*args, **kwargs)
        self.shape_ids.append(shape_id)  # Store shape id
        return shape_id

    def draw_polygon(self, *args, **kwargs):
        kwargs['fill'] = self.adjust_alpha(kwargs.get('fill', ''), self.shape_alpha)
        shape_id = self.create_polygon(*args, **kwargs)
        self.shape_ids.append(shape_id)  # Store shape id
        return shape_id

    def draw_line(self, *args, **kwargs):
        kwargs['fill'] = self.adjust_alpha(kwargs.get('fill', ''), self.shape_alpha)
        shape_id = self.create_line(*args, **kwargs)
        self.shape_ids.append(shape_id)  # Store shape id
        return shape_id

    def adjust_alpha(self, color, alpha):
        if color.startswith('#'):
            r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
            return f'#{r:02x}{g:02x}{b:02x}'
        return color

    def redraw_shapes(self):
        self.delete("all")  # Clear canvas
        # print('in redraw_shapes for window '+self.positionName)

        self.shape_ids = []  # Reset shape ids
        # Draw shapes on the canvas
        # if self.positionName == 'NORTH':
        # rectangle = canN.draw_rectangle(750+int(100*self.shape_alpha), 0, 800, 50, fill=RED, outline='')  # Rectangle
        rectangle = canN.draw_rectangle(int(screen_width / 2.0), 0, int(screen_width / 2.0) + int(10*square_size*self.shape_alpha),
                                          int(10*square_size*self.shape_alpha), fill=RED, outline='')  # Rectangle

        # elif self.positionName == 'EAST':
        #     # circle = canvas.draw_oval(0, 0, 350, 200, fill=GREEN, outline='')  # Circle
        #     rectangle = canvas.draw_rectangle(0, 750, 50, 800, fill=GREEN, outline='')  # Rectangle
        # elif self.positionName == 'SOUTH':
        #     # triangle = canvas.draw_polygon(450, 50, 550, 50, 500, 150, fill=BLUE, outline='')  # Triangle
        #     # rectangle = canvas.draw_rectangle(0, 0, 50, 50, fill=BLUE, outline='')  # Rectangle
        #     rectangle = canvas.draw_rectangle(750, 0, 800, 50, fill=BLUE, outline='')  # Rectangle
        # elif self.positionName == 'WEST':
        #     # ellipse = canvas.draw_oval(600, 50, 750, 150, fill=YELLOW, outline='')  # Ellipse
        #     rectangle = canvas.draw_rectangle(0, 0, 50, 50, fill=YELLOW, outline='')  # Rectangle

# Function to update window transparency
def update_n_window_transparency(value):
    alpha = float(value) / 100  # Convert slider value to alpha value
    winN.attributes("-alpha", alpha)

# Function to update shape transparency
def update_n_shape_transparency(value):
    canN.set_shape_alpha(value)

def moveRec(canTemp, name, shape_id, dx, dy, direction):
    # print('in moveRec for name ', name)
    x1, y1, x2, y2 = canTemp.coords(shape_id)
    if name == 'N' or name == 'S':
        canTemp.move(shape_id, dx * direction, 0)
        if x1 <= 0 or x2 > canTemp.winfo_width():  # Reverse direction at canvas boundaries
            direction *= -1
            canTemp.move(shape_id, dx * direction, 0)
            canTemp.move(shape_id, dx * direction, 0)

    elif name == 'E' or name == 'W':
        canTemp.move(shape_id, 0, dy * direction)
        if y1 <= 0 or y2 > canTemp.winfo_height():  # Reverse direction at canvas boundaries
            direction *= -1
            canTemp.move(shape_id, 0, dy * direction)
            canTemp.move(shape_id, 0, dy * direction)

    canTemp.update()
    # print('x1, y1, x2, y2 : ', x1, y1, x2, y2)
    # print('canN.winfo_width() : ', canN.winfo_width())
        # print('change direction : ', direction)

    # if name == 'N' or name == 'S':
    #     elif name == 'E' or name =='W':
        # canN.after(50)  # Delay between animation steps in milliseconds
    return direction

# Function to animate shape movement
def animate_shape():
    global is_animating
    global animation_mode
    animation_mode = animation_mode%8  # reset beyond 10
    animation_mode += 1
    # print('animate_shape for animation_mode : ', animation_mode)
    # print('animate_shape for is_animating : ', is_animating)
    if not is_animating:
        is_animating = True
        dx = 5  # Change in x-coordinate per animation step
        dy = 5  # Change in x-coordinate per animation step
        directionN = 1  # Initial direction of movement
        directionE = 1  # Initial direction of movement
        directionS = 1  # Initial direction of movement
        directionW = 1  # Initial direction of movement
        while is_animating:
            for _ in range(10):  # Number of animation steps

                for shape_id in canN.shape_ids:
                    directionN = moveRec(canN, 'N', shape_id, dx, dy, directionN)
                if animation_mode >=3:
                    for shape_id in canE.shape_ids:
                        directionE = moveRec(canE, 'E', shape_id, dx, dy, directionE)
                if animation_mode >=5:
                    for shape_id in canS.shape_ids:
                        directionS = moveRec(canS, 'S', shape_id, dx, dy, directionS)
                if animation_mode >=7:
                    for shape_id in canW.shape_ids:
                        directionW = moveRec(canW, 'W', shape_id, dx, dy, directionW)

                canN.update()

                canN.after(5)  # Delay between animation steps in milliseconds

    else:
        if animation_mode%2 == 0:
            is_animating = False
        # animation_mode = 0


# Function to handle shape click event
def shape_click_n(event):
    x, y = event.x, event.y
    name = 'N'
    # clicked_shape = canN.find_closest(x, y)  # Find the shape closest to the click position
    print(name, " - Clicked shape at coord : {}, {}".format(x, y))

    clicked_shape = canN.find_closest(x, y)  # Find the shape closest to the click position
    print(name, " - Clicked shape_id :", clicked_shape)


# Function to handle shape click event
def shape_click_e(event):
    x, y = event.x, event.y
    name = 'E'
    # clicked_shape = canN.find_closest(x, y)  # Find the shape closest to the click position
    print(name, " - Clicked shape at coord : {}, {}".format(x, y))

    clicked_shape = canE.find_closest(x, y)  # Find the shape closest to the click position
    print(name, " - Clicked shape_id :", clicked_shape)


# Function to handle shape click event
def shape_click_s(event):
    x, y = event.x, event.y
    name = 'S'
    # clicked_shape = canN.find_closest(x, y)  # Find the shape closest to the click position
    print(name, " - Clicked shape at coord : {}, {}".format(x, y))

    clicked_shape = canS.find_closest(x, y)  # Find the shape closest to the click position
    print(name, " - Clicked shape_id :", clicked_shape)


# Function to handle shape click event
def shape_click_w(event):
    x, y = event.x, event.y
    name = 'W'
    # clicked_shape = canN.find_closest(x, y)  # Find the shape closest to the click position
    print(name, " - Clicked shape at coord : {}, {}".format(x, y))

    clicked_shape = canW.find_closest(x, y)  # Find the shape closest to the click position
    print(name, " - Clicked shape_id :", clicked_shape)

# Create a Tkinter window
def createWindows(name):
    global screen_width
    global screen_height
    window = tk.Tk()
    titleTemp = "Borderless Rectangle {}".format(name)
    window.title(titleTemp)
    print('Creating '+titleTemp)

    # # Set the window to full screen
    # window.attributes("-fullscreen", True)

    # Get screen width and height
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()

    print('screen dimensions : (width, height) = ', screen_width, ' , ', screen_height)
    # Set up the canvas
    # canvas = tk.Canvas(window, width=screen_width, height=screen_height,
    # Make the window borderless
    window.overrideredirect(True)

    # Set the window dimensions and position
    # window.geometry("800x600+100+100")  # Width x Height + X offset + Y offset



    # Set up the canvas
    canvas = TransparentCanvas(window, bg='black', highlightthickness=0)
    window.wm_attributes("-transparentcolor", "black")
    canvas.pack(fill=tk.BOTH, expand=True)




    # Draw shapes on the canvas
    if name == 'NORTH':
        rectangle = canvas.draw_rectangle(int(screen_width/2.0), 0, int(screen_width/2.0)+square_size, square_size, fill=RED, outline='')  # Rectangle
        # Create a slider to adjust window transparency
        window_transparency_slider = tk.Scale(window, from_=0, to=100, orient=tk.HORIZONTAL, command=update_n_window_transparency)
        window_transparency_slider.pack(fill=tk.X)

        # Create a slider to adjust shape transparency
        shape_transparency_slider = tk.Scale(window, from_=0, to=100, orient=tk.HORIZONTAL, command=update_n_shape_transparency)
        shape_transparency_slider.pack(fill=tk.X)
        # Create a button to toggle animation
        animate_button = tk.Button(window, text="Toggle Animation (P)", command=animate_shape)
        animate_button.pack()

        # Bind key press event to window
        window.bind("p", lambda event: animate_shape())

        # Set the window dimensions and position
        window.geometry("2560x500")  # Width x Height + X offset + Y offset
        window.geometry("{}x{}".format(screen_width, window_size))  # Width x Height + X offset + Y offset

        # Bind mouse click event to canvas_n
        canvas.bind("<Button-1>", shape_click_n)
    elif name == 'EAST':
        # circle = canvas.draw_oval(0, 0, 350, 200, fill=GREEN, outline='')  # Circle
        # rectangle = canvas.draw_rectangle(100, 0, square_size, square_size, fill=GREEN, outline='')  # Rectangle
        rectangle = canvas.draw_rectangle(window_size-square_size, int(screen_height / 2.0) - int(square_size / 2.0), window_size,
                                          int(screen_height / 2.0) + int(square_size / 2.0), fill=GREEN,
                                          outline='')  # Rectangle

        window.geometry("{}x{}+{}+0".format(window_size, screen_height, screen_width-window_size))  # Width x Height + X offset + Y offset
        # Bind mouse click event to canvas_e
        canvas.bind("<Button-1>", shape_click_e)
    elif name == 'SOUTH':
        # triangle = canvas.draw_polygon(450, 50, 550, 50, 500, 150, fill=BLUE, outline='')  # Triangle
        # rectangle = canvas.draw_rectangle(0, 0, 50, 50, fill=BLUE, outline='')  # Rectangle

        window.geometry("{}x{}+0+{}".format(screen_width, window_size, screen_height-window_size))  # Width x Height + X offset + Y offset
        rectangle = canvas.draw_rectangle(int(screen_width/2.0), window_size-square_size, int(screen_width/2.0)+square_size, window_size, fill=BLUE, outline='')  # Rectangle
        # Bind mouse click event to canvas_s
        canvas.bind("<Button-1>", shape_click_s)
    elif name == 'WEST':
        # ellipse = canvas.draw_oval(600, 50, 750, 150, fill=YELLOW, outline='')  # Ellipse
        rectangle = canvas.draw_rectangle(0, int(screen_height/2.0)-int(square_size/2.0), square_size, int(screen_height/2.0)+int(square_size/2.0), fill=YELLOW, outline='')  # Rectangle
        window.geometry("{}x{}+0+0".format(window_size, screen_height))  # Width x Height + X offset + Y offset
        # Bind mouse click event to canvas_w
        canvas.bind("<Button-1>", shape_click_w)



    return window, canvas

screen_width = 0
screen_height = 0
is_animating = False  # Flag to control animation state
animation_mode = 0
# Run the Tkinter event loop
print('Creating windows')
winN, canN = createWindows('NORTH')
winE, canE = createWindows('EAST')
winS, canS = createWindows('SOUTH')
winW, canW = createWindows('WEST')
print('Starting winN')
winN.mainloop()
# print('Starting winE')
# winE.mainloop()
print('Done')