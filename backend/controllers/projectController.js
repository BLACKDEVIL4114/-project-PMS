const Project = require('../models/Project');

// @desc    Get all projects
// @route   GET /api/projects
// @access  Private
exports.getProjects = async (req, res) => {
  try {
    const projects = await Project.find({}).populate('manager', 'name email').populate('teamLeader', 'name email');
    res.json(projects);
  } catch (error) {
    res.status(500).json({ message: error.message });
  }
};

// @desc    Get single project
// @route   GET /api/projects/:id
// @access  Private
exports.getProjectById = async (req, res) => {
  try {
    const project = await Project.findById(req.params.id).populate('manager', 'name email').populate('teamLeader', 'name email');
    if (project) {
      res.json(project);
    } else {
      res.status(404).json({ message: 'Project not found' });
    }
  } catch (error) {
    res.status(500).json({ message: error.message });
  }
};

// @desc    Create a project
// @route   POST /api/projects
// @access  Private/Admin/Manager
exports.createProject = async (req, res) => {
  const { name, description, manager, teamLeader, status, startDate, endDate } = req.body;
  try {
    const project = new Project({ name, description, manager, teamLeader, status, startDate, endDate });
    const createdProject = await project.save();
    res.status(201).json(createdProject);
  } catch (error) {
    res.status(400).json({ message: error.message });
  }
};

// @desc    Update project
// @route   PUT /api/projects/:id
// @access  Private/Admin/Manager
exports.updateProject = async (req, res) => {
  const { name, description, manager, teamLeader, status, startDate, endDate } = req.body;
  try {
    const project = await Project.findById(req.params.id);
    if (project) {
      project.name = name || project.name;
      project.description = description || project.description;
      project.manager = manager || project.manager;
      project.teamLeader = teamLeader || project.teamLeader;
      project.status = status || project.status;
      project.startDate = startDate || project.startDate;
      project.endDate = endDate || project.endDate;

      const updatedProject = await project.save();
      res.json(updatedProject);
    } else {
      res.status(404).json({ message: 'Project not found' });
    }
  } catch (error) {
    res.status(400).json({ message: error.message });
  }
};

// @desc    Delete project
// @route   DELETE /api/projects/:id
// @access  Private/Admin
exports.deleteProject = async (req, res) => {
  try {
    const project = await Project.findById(req.params.id);
    if (project) {
      await project.deleteOne();
      res.json({ message: 'Project removed' });
    } else {
      res.status(404).json({ message: 'Project not found' });
    }
  } catch (error) {
    res.status(500).json({ message: error.message });
  }
};
