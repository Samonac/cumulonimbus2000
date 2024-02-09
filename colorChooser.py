import tkinter as tk
import tkinter.colorchooser as colorchooser

# Define the weather dictionary
weatherDict = {
    'SUNNY': [(135, 206, 250), (255, 255, 0)],
    'PARTLY_CLOUDY': [(200, 200, 200), (180, 180, 180)],
    'CLOUDY': [(150, 150, 150), (155, 155, 155)],
    'VERY_CLOUDY': [(100, 100, 100), (105, 105, 105)],
    'FOG': [(180, 180, 180), (170, 170, 170)],
    'LIGHT_SHOWERS': [(190, 190, 190), (200, 200, 210)],
    'LIGHT_SLEET_SHOWERS': [(195, 195, 195), (205, 205, 205)],
    'LIGHT_SLEET': [(185, 185, 185), (195, 195, 195)],
    'THUNDERY_SHOWERS': [(105, 105, 120), (100, 100, 115)],
    'LIGHT_SNOW': [(215, 215, 215), (225, 225, 225)],
    'HEAVY_SNOW': [(90, 90, 90), (80, 80, 80)],
    'LIGHT_RAIN': [(135, 206, 250), (140, 220, 255)],
    'HEAVY_SHOWERS': [(100, 100, 115), (95, 95, 110)],
    'HEAVY_RAIN': [(95, 95, 95), (90, 90, 90)],
    'LIGHT_SNOW_SHOWERS': [(155, 155, 155), (160, 160, 160)],
    'HEAVY_SNOW_SHOWERS': [(80, 80, 80), (70, 70, 70)],
    'THUNDERY_HEAVY_RAIN': [(145, 145, 145), (140, 140, 140)],
    'THUNDERY_SNOW_SHOWERS': [(70, 70, 70), (60, 60, 60)]
}

root = tk.Tk()
root.title("Weather Colors")




# Function to display the colors
def display_colors():

    keys = list(weatherDict.keys())
    index = 0

    def show_color():
        canvas.delete("all")
        canvas.create_rectangle(0, 0, 100, 100, fill='#%02x%02x%02x' % weatherDict[keys[index]][0])
        canvas.create_rectangle(100, 0, 200, 100, fill='#%02x%02x%02x' % weatherDict[keys[index]][1])
        label.config(text=keys[index])

    def next_color():
        nonlocal index
        if index < len(keys) - 1:
            index += 1
        else:
            index = 0
        show_color()

    def prev_color():
        nonlocal index
        if index > 0:
            index -= 1
        else:
            index = len(keys) - 1
        show_color()

    def show_all_colors():
        new_window = tk.Toplevel()
        new_window.title("All Colors")

        # for i, key in enumerate(keys):
        #     color_frame = tk.Frame(new_window, bg='#%02x%02x%02x' % weatherDict[key][0], width=200, height=100)
        #     color_frame.pack(side=tk.TOP, fill=tk.X)
        #     color_frame.pack_propagate(False)
        #
        #     color_label = tk.Label(color_frame, text=key, bg='#%02x%02x%02x' % weatherDict[key][1], padx=10, pady=5)
        #     color_label.pack(fill=tk.BOTH, expand=True)




        rows = 4
        columns = 5
        padding = 5

        for i, (key, colors) in enumerate(weatherDict.items()):
            row = i // columns
            column = i % columns

            frame = tk.Frame(new_window, width=100, height=100, padx=padding, pady=padding)
            frame.grid(row=row, column=column, padx=padding, pady=padding)
            frame.grid_propagate(False)

            canvas = tk.Canvas(frame, width=90, height=90)
            canvas.pack(fill=tk.BOTH, expand=True)

            canvas.create_rectangle(0, 0, 90, 45, fill='#%02x%02x%02x' % colors[0])
            canvas.create_rectangle(0, 45, 90, 90, fill='#%02x%02x%02x' % colors[1])

            label = tk.Label(frame, text=key, bg='white')
            label.pack(fill=tk.X)

    def display_all_colors():
        def on_color_click(event):
            for key, (rgb1, rgb2) in color_map.items():
                if event.widget == color_widgets[key]:
                    color = colorchooser.askcolor(initialcolor=rgb1 if event.y < 45 else rgb2)
                    if color[1]:
                        new_rgb = tuple(int(x) for x in color[0])
                        color_map[key] = new_rgb if event.y < 45 else (rgb1, new_rgb[1], new_rgb[2])
                        event.widget.config(bg='#%02x%02x%02x' % color_map[key])

        all_colors_window = tk.Toplevel()
        all_colors_window.title("All Colors")

        rows = 4
        columns = 5
        padding = 5

        color_map = {key: colors for key, colors in weatherDict.items()}

        color_widgets = {}

        for i, (key, colors) in enumerate(color_map.items()):
            row = i // columns
            column = i % columns

            frame = tk.Frame(all_colors_window, width=100, height=100, padx=padding, pady=padding)
            frame.grid(row=row, column=column, padx=padding, pady=padding)
            frame.grid_propagate(False)

            canvas = tk.Canvas(frame, width=90, height=90)
            canvas.pack(fill=tk.BOTH, expand=True)

            canvas.create_rectangle(0, 0, 90, 45, fill='#%02x%02x%02x' % colors[0])
            canvas.create_rectangle(0, 45, 90, 90, fill='#%02x%02x%02x' % colors[1])

            label = tk.Label(frame, text=key, bg='white')
            label.pack(fill=tk.X)

            frame.bind('<Button-1>', on_color_click)
            color_widgets[key] = frame


    canvas = tk.Canvas(root, width=200, height=100)
    canvas.pack()

    label = tk.Label(root, text=keys[index])
    label.pack()

    prev_button = tk.Button(root, text="Previous", command=prev_color)
    prev_button.pack(side=tk.LEFT)

    next_button = tk.Button(root, text="Next", command=next_color)
    next_button.pack(side=tk.RIGHT)

    all_colors_button = tk.Button(root, text="Show All Colors", command=display_all_colors)
    all_colors_button.pack()

    show_color()

    root.mainloop()



# Function to display all colors in a grid
def old_display_all_colors():
    all_colors_window = tk.Toplevel()
    all_colors_window.title("All Colors")

    rows = 4
    columns = 5
    padding = 5

    for i, (key, colors) in enumerate(weatherDict.items()):
        row = i // columns
        column = i % columns

        frame = tk.Frame(all_colors_window, width=100, height=100, padx=padding, pady=padding)
        frame.grid(row=row, column=column, padx=padding, pady=padding)
        frame.grid_propagate(False)

        canvas = tk.Canvas(frame, width=90, height=45)
        canvas.pack(fill=tk.BOTH, expand=True)

        canvas.create_rectangle(0, 0, 90, 45, fill='#%02x%02x%02x' % colors[0])
        canvas.create_rectangle(0, 45, 90, 90, fill='#%02x%02x%02x' % colors[1])

        label = tk.Label(frame, text=key, bg='white')
        label.pack(fill=tk.X)


# Display the colors
display_colors()



# Display all colors in a grid
#display_all_colors()
