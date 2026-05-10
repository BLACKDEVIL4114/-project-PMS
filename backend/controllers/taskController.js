const Task = require('../models/Task');

// @desc    Get all tasks
// @route   GET /api/tasks
// @access  Private
exports.getTasks = async (req, res) => {
  try {
    const tasks = await Task.find({}).populate('project', 'name').populate('assignedTo', 'name email');
    res.json(tasks);
  } catch (error) {
    res.status(500).json({ message: error.message });
  }
};

// @desc    Get single task
// @route   GET /api/tasks/:id
// @access  Private
exports.getTaskById = async (req, res) => {
  try {
    const task = await Task.findById(req.params.id).populate('project', 'name').populate('assignedTo', 'name email');
    if (task) {
      res.json(task);
    } else {
      res.status(404).json({ message: 'Task not found' });
    }
  } catch (error) {
    res.status(500).json({ message: error.message });
  }
};

// @desc    Create a task
// @route   POST /api/tasks
// @access  Private/Admin/Manager/Team Leader
exports.createTask = async (req, res) => {
  const { title, description, project, assignedTo, priority, status, dueDate } = req.body;
  try {
    const task = new Task({ title, description, project, assignedTo, priority, status, dueDate });
    const createdTask = await task.save();
    res.status(201).json(createdTask);
  } catch (error) {
    res.status(400).json({ message: error.message });
  }
};

// @desc    Update task status or other fields
// @route   PUT /api/tasks/:id
// @access  Private
exports.updateTask = async (req, res) => {
  const { title, description, assignedTo, priority, status, dueDate, completedDate } = req.body;
  try {
    const task = await Task.findById(req.params.id);
    if (task) {
      task.title = title || task.title;
      task.description = description || task.description;
      task.assignedTo = assignedTo || task.assignedTo;
      task.priority = priority || task.priority;
      task.status = status || task.status;
      task.dueDate = dueDate || task.dueDate;
      task.completedDate = completedDate || task.completedDate;

      if (status === 'Completed' && !task.completedDate) {
        task.completedDate = new Date();
      }

      const updatedTask = await task.save();
      res.json(updatedTask);
    } else {
      res.status(404).json({ message: 'Task not found' });
    }
  } catch (error) {
    res.status(400).json({ message: error.message });
  }
};

// @desc    Delete task
// @route   DELETE /api/tasks/:id
// @access  Private/Admin/Manager
exports.deleteTask = async (req, res) => {
  try {
    const task = await Task.findById(req.params.id);
    if (task) {
      await task.deleteOne();
      res.json({ message: 'Task removed' });
    } else {
      res.status(404).json({ message: 'Task not found' });
    }
  } catch (error) {
    res.status(500).json({ message: error.message });
  }
};
