import subprocess
import threading
from flask import Flask, jsonify, request


app = Flask(__name__)

# Dictionary to store running tasks and their corresponding threads
running_tasks = {}
# Example data
tasks = [
    {
        'id': 1,
        'title': 'movie_to_cloud_pngAnalyzer',
        'description': 'Convert png to jsonDict for cloud',
        'done': False,
        'python_script_path': 'movie_to_cloud_pngAnalyzer.py',
        'timeout': 10  # Timeout in seconds
    },
    {
        'id': 2,
        'title': 'Build a RESTful API',
        'description': 'Build a RESTful API using Flask',
        'done': False,
        'python_script_path': 'show_things_on_screen.py',
        'timeout': None  # No timeout : script will just be launched, and that's it.
    },    {
        'id': 3,
        'title': 'Launch Squares with output',
        'description': 'Launch Squares with output',
        'done': False,
        'python_script_path': 'show_things_on_screen.py',
        'timeout': -1  # No timeout, and (normally ?) get real-time output. No way to stop the executed script though.
    },
    {
        'id': 4,
        'title': 'control_tv',
        'description': 'Control TV',
        'done': False,
        'python_script_path': 'control_tv.py',
        'timeout': 10  # Timeout in seconds
    },
    {
        'id': 5,
        'title': 'control_lights_phue',
        'description': 'Control Philips Hue lights',
        'done': False,
        'python_script_path': 'calcifer.py',
        'timeout': None  # No timeout, and (normally ?) get real-time output. No way to stop the executed script though.
    },
    {
        'id': 6,
        'title': 'control_wand',
        'description': 'Send/Receive controls to the MagicWand (including IR, hopefully soon)',
        'done': False,
        'python_script_path': 'control_wand.py',
        'timeout': None  # No timeout : script will just be launched, and that's it.
    }
]



# Get all tasks
@app.route('/tasks', methods=['GET'])
def get_tasks():
    return jsonify({'tasks': tasks})


# Get a single task by id
@app.route('/tasks/<int:task_id>', methods=['GET'])
def get_task(task_id):
    task = [task for task in tasks if task['id'] == task_id]
    if len(task) == 0:
        return jsonify({'error': 'Task not found'}), 404
    return jsonify({'task': task[0]})


# Create a new task
@app.route('/tasks', methods=['POST'])
def create_task():
    if not request.json or not 'title' in request.json:
        return jsonify({'error': 'Title is required'}), 400
    task = {
        'id': tasks[-1]['id'] + 1,
        'title': request.json['title'],
        'description': request.json.get('description', ""),
        'done': False,
        'python_script_path': request.json.get('python_script_path', ""),
        'timeout': request.json.get('timeout', None)
    }
    tasks.append(task)
    return jsonify({'task': task}), 201


# Update a task
@app.route('/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    task = [task for task in tasks if task['id'] == task_id]
    if len(task) == 0:
        return jsonify({'error': 'Task not found'}), 404
    if not request.json:
        return jsonify({'error': 'Data not provided'}), 400
    task[0]['title'] = request.json.get('title', task[0]['title'])
    task[0]['description'] = request.json.get('description', task[0]['description'])
    task[0]['done'] = request.json.get('done', task[0]['done'])
    task[0]['python_script_path'] = request.json.get('python_script_path', task[0]['python_script_path'])
    task[0]['timeout'] = request.json.get('timeout', task[0]['timeout'])
    return jsonify({'task': task[0]})


# Delete a task
@app.route('/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    task = [task for task in tasks if task['id'] == task_id]
    if len(task) == 0:
        return jsonify({'error': 'Task not found'}), 404
    task_obj = running_tasks.get(task_id)
    if task_obj:
        task_obj.terminate()  # Interrupt the thread if it's running
        del running_tasks[task_id]  # Remove the task from the running_tasks dictionary
    tasks.remove(task[0])
    return jsonify({'result': True})


# Function to execute script with a timeout
def execute_script_with_timeout(task_id, script_path, timeout, params=None):
    try:
        command = ['python', script_path]
        if params:
            command.extend(params)
        if timeout == -1:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            running_tasks[task_id] = process  # Add the task to the running_tasks dictionary
            output, errors = process.communicate()
            del running_tasks[task_id]  # Remove the task from the running_tasks dictionary after execution

            return {'output': output.decode('utf-8'), 'errors': errors.decode('utf-8'), 'id': task_id}, 200
        else:
            output = subprocess.check_output(command, stderr=subprocess.STDOUT, timeout=timeout,
                                             universal_newlines=True)
            return {'output': output, 'id': task_id}, 200
    except subprocess.CalledProcessError as e:
        return {'error': 'Script execution failed', 'output': e.output}, 500
    except subprocess.TimeoutExpired:
        return {'error': 'Script execution timed out'}, 500


# Execute a Python script
@app.route('/execute_script/<int:task_id>', methods=['POST'])
def execute_script(task_id):
    task = [task for task in tasks if task['id'] == task_id]
    if len(task) == 0:
        return jsonify({'error': 'Task not found'}), 404
    script_path = task[0]['python_script_path']
    timeout = task[0]['timeout']
    if not script_path:
        return jsonify({'error': 'No script path provided for this task'}), 400

    params = request.json.get('params', [])
    print('params are : ', params)
    print('of type  : ', type(params))

    if timeout is not None:
        print('max timeout : ', timeout)
        return execute_script_with_timeout(script_path, timeout, params)
    else:
        # No timeout specified, run script in a separate thread
        print('new thread')
        # thread = threading.Thread(target=execute_script_with_timeout, args=(script_path, None, params))
        thread = threading.Thread(target=execute_script_with_timeout, args=(script_path, None, params))
        thread.start()
        running_tasks[task_id] = thread  # Add the task to the running_tasks dictionary
        return jsonify({'output': 'Script execution started in the background', 'id': task_id}), 200


if __name__ == '__main__':
    app.run(debug=True)
