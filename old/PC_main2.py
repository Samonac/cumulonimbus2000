import tkinter as tk


# Define some colors
RED = "#FF0000"
GREEN = "#00FF00"
BLUE = "#0000FF"
YELLOW = "#FFFF00"
WHITE = "#FFFFFF"

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
        self.shape_ids = []  # Reset shape ids
        # Draw shapes on the canvas
        rectangle = self.draw_rectangle(50, 50, 150, 150, fill=RED, outline='')  # Rectangle
        circle = self.draw_oval(250, 100, 350, 200, fill=GREEN, outline='')  # Circle
        triangle = self.draw_polygon(450, 50, 550, 50, 500, 150, fill=BLUE, outline='')  # Triangle
        ellipse = self.draw_oval(600, 50, 750, 150, fill=YELLOW, outline='')  # Ellipse

# Function to update window transparency
def update_window_transparency(value):
    alpha = float(value) / 100  # Convert slider value to alpha value
    winN.attributes("-alpha", alpha)

# Function to update shape transparency
def update_shape_transparency(value):
    canN.set_shape_alpha(value)

# Function to handle shape click event
def shape_click(event):
    x, y = event.x, event.y
    clicked_shape = canvas.find_closest(x, y)  # Find the shape closest to the click position
    print("Clicked shape:", clicked_shape)

# Create a Tkinter window
def createWindows(name):
    window = tk.Tk()
    titleTemp = "Borderless Rectangle {}".format(name)
    window.title(titleTemp)
    print('Creating '+titleTemp)

    # Make the window borderless
    window.overrideredirect(True)

    # Set up the canvas
    canvas = TransparentCanvas(window, bg='black', highlightthickness=0)
    window.wm_attributes("-transparentcolor", "black")
    canvas.pack(fill=tk.BOTH, expand=True)

    # Bind mouse click event to canvas
    canvas.bind("<Button-1>", shape_click)

    return window, canvas

# Run the Tkinter event loop
winN, canN = createWindows('NORTH')
winN.mainloop()
