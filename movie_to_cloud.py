import cv2
import numpy as np
from sklearn.cluster import KMeans
import matplotlib.pyplot as plt


def extract_main_colors(image, num_colors=5):
    # Reshape the image to be a list of pixels
    pixels = image.reshape((-1, 3))

    # Convert to float
    pixels = np.float32(pixels)

    # Perform KMeans clustering
    kmeans = KMeans(n_clusters=num_colors)
    kmeans.fit(pixels)

    # Get the main colors
    main_colors = kmeans.cluster_centers_

    return main_colors.astype(int)


def show_main_colors(image, main_colors):
    # Create a blank image to display the main colors
    color_display = np.zeros((100, 300, 3), dtype=np.uint8)

    # Fill rectangles with each main color
    start = 0
    for color in main_colors:
        end = start + 300 // len(main_colors)
        cv2.rectangle(color_display, (start, 0), (end, 100), color.tolist(), -1)
        start = end

    # Display the image with main colors
    plt.imshow(cv2.cvtColor(color_display, cv2.COLOR_BGR2RGB))
    plt.axis('off')
    plt.show()


def process_video(video_path, interval=5):
    # Open the video file
    cap = cv2.VideoCapture(video_path)

    # Get the frame rate of the video
    fps = cap.get(cv2.CAP_PROP_FPS)

    # Calculate the number of frames to skip
    frames_to_skip = int(fps * interval)

    # Process frames
    frame_number = 0
    while cap.isOpened():
        # Set frame position
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)

        # Read the frame
        ret, frame = cap.read()

        if ret:
            # Convert frame to RGB (OpenCV uses BGR)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Extract main colors
            main_colors = extract_main_colors(frame_rgb)

            # Show main colors
            show_main_colors(frame_rgb, main_colors)

            # Skip frames
            frame_number += frames_to_skip
        else:
            break

    # Release video capture
    cap.release()


import cv2


def save_frames(video_path, output_folder, interval=1):
    # Open the video file
    cap = cv2.VideoCapture(video_path)

    # Get the frame rate of the video
    fps = cap.get(cv2.CAP_PROP_FPS)

    # Calculate the number of frames to skip
    frames_to_skip = int(fps * interval)

    # Process frames
    frame_number = 0
    while cap.isOpened():
        # Set frame position
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)

        # Read the frame
        ret, frame = cap.read()

        if ret:
            # Save the frame as PNG
            cv2.imwrite(f"{output_folder}/frame_{frame_number // int(fps)}.png", frame)

            # Skip frames
            frame_number += frames_to_skip
        else:
            break

    # Release video capture
    cap.release()


if __name__ == "__main__":
    # video_path = input("Enter the path to the input video file: ")
    # output_folder = input("Enter the path to the output folder: ")
    output_folder = 'D:/Videos/Frames/'
    # interval = int(input("Enter the time interval (in seconds): "))

# if __name__ == "__main__":
    # video_path = input("Enter the path to the input video file: ")
    # interval = int(input("Enter the time interval (in seconds): "))
    interval = 1
    # video_path = input("Enter the path to the input video file: ")
    # video_path = 'D:/Videos/ambi_test.mp4'
    video_path = 'D:/Videos/EIGHTHGRADE_gl00bysw0rld082218.mov.mp4'
    # 'mario_kart_tribue'
    # num_frames = int(input("Enter the number of frames to process: "))
    # num_frames = 1000
    # process_video(video_path, num_frames)

    save_frames(video_path, output_folder, interval)
    process_video(video_path, interval)