import { useState, useEffect } from 'react';
import { Modal } from '../common/Modal';
import { Button } from '../common/Button';
import { Input, Textarea, Select } from '../common/FormControls';
import { useApp } from '../../context/AppContext';
import { TASK_TYPES } from '../../constants/theme';
import { getTodayString } from '../../utils/dateUtils';

const getDefaultTaskForm = () => {
  const today = getTodayString();
  return {
    title: '',
    description: '',
    taskType: 'Daily',
    category: 'Coding',
    priority: 'Medium',
    status: 'Pending',
    startDate: today,
    dueDate: today,
    associatedGoalId: '',
  };
};

export function TaskModal({ isOpen, onClose, editingTask }) {
  const { addTask, updateTask, goals } = useApp();

  const [formData, setFormData] = useState(getDefaultTaskForm);

  const [errors, setErrors] = useState({});

  useEffect(() => {
    if (editingTask) {
      setFormData({
        title: editingTask.title || '',
        description: editingTask.description || '',
        taskType: editingTask.taskType || 'Daily',
        category: editingTask.category || 'Coding',
        priority: editingTask.priority || 'Medium',
        status: editingTask.status || 'Pending',
        startDate: editingTask.startDate || getTodayString(),
        dueDate: editingTask.dueDate || getTodayString(),
        associatedGoalId: editingTask.associatedGoalId || '',
      });
    } else {
      setFormData(getDefaultTaskForm());
    }
    setErrors({});
  }, [editingTask, isOpen]);

  const handleChange = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    if (errors[field]) {
      setErrors((prev) => ({ ...prev, [field]: null }));
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const newErrors = {};

    if (!formData.title.trim()) {
      newErrors.title = 'Task title is required';
    } else if (formData.title.trim().length > 120) {
      newErrors.title = 'Task title must be 120 characters or fewer';
    }

    if (!formData.startDate) {
      newErrors.startDate = 'Start date is required';
    }
    if (!formData.dueDate) {
      newErrors.dueDate = 'Due date is required';
    } else if (formData.startDate && formData.dueDate < formData.startDate) {
      newErrors.dueDate = 'Due date cannot be earlier than start date';
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    const selectedGoal = goals.find((g) => g.id === formData.associatedGoalId);
    const taskPayload = {
      ...formData,
      associatedGoalTitle: selectedGoal ? selectedGoal.title : null,
    };

    if (editingTask) {
      updateTask({ ...editingTask, ...taskPayload });
    } else {
      addTask(taskPayload);
    }
  };

  const categoryOptions = [
    { value: 'Academic', label: 'Academic & Courses' },
    { value: 'Coding', label: 'Coding & Tech' },
    { value: 'Career', label: 'Career & Research' },
    { value: 'Reading', label: 'Reading & Learning' },
    { value: 'Health', label: 'Health & Fitness' },
    { value: 'Personal', label: 'Personal' },
  ];

  const priorityOptions = [
    { value: 'High', label: 'High Priority' },
    { value: 'Medium', label: 'Medium Priority' },
    { value: 'Low', label: 'Low Priority' },
  ];

  const statusOptions = [
    { value: 'Pending', label: 'Pending' },
    { value: 'In Progress', label: 'In Progress' },
    { value: 'Completed', label: 'Completed' },
  ];

  const goalOptions = [
    { value: '', label: 'None (Standalone Task)' },
    ...goals.map((g) => ({
      value: g.id,
      label: `${g.type === 'Long-Term' ? '🎯 [Long-Term]' : '⚡ [Short-Term]'} ${g.title}`,
    })),
  ];

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={editingTask ? 'Edit Task' : 'Create New Task'}
      subtitle={
        editingTask
          ? 'Update your task details, timeline, and associated goal'
          : 'Define a task to organize your academic and personal life'
      }
      size="lg"
      footer={
        <>
          <Button variant="outline" size="md" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" size="md" onClick={handleSubmit}>
            {editingTask ? 'Save Changes' : 'Create Task'}
          </Button>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* 1. Title */}
        <Input
          label="1. Task Title"
          id="task-title"
          placeholder="e.g., Solve 3 LeetCode Graph problems / Submit OS Lab"
          value={formData.title}
          onChange={(e) => handleChange('title', e.target.value)}
          required
          error={errors.title}
        />

        {/* 2. Description */}
        <Textarea
          label="2. Description"
          id="task-description"
          placeholder="Provide context, references, lecture links, or specific requirements..."
          value={formData.description}
          onChange={(e) => handleChange('description', e.target.value)}
          rows={3}
        />

        {/* 3 & 4. Task Type & Category */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Select
            label="3. Task Type"
            id="task-type"
            value={formData.taskType}
            onChange={(e) => handleChange('taskType', e.target.value)}
            options={TASK_TYPES.map((t) => ({ value: t.id, label: t.label }))}
            required
            helperText="Daily, Short-Term, Long-Term, One-Time, or Occasional"
          />

          <Select
            label="4. Category"
            id="task-category"
            value={formData.category}
            onChange={(e) => handleChange('category', e.target.value)}
            options={categoryOptions}
            required
          />
        </div>

        {/* 5 & 6. Priority & Status */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Select
            label="5. Priority"
            id="task-priority"
            value={formData.priority}
            onChange={(e) => handleChange('priority', e.target.value)}
            options={priorityOptions}
            required
          />

          <Select
            label="6. Status"
            id="task-status"
            value={formData.status}
            onChange={(e) => handleChange('status', e.target.value)}
            options={statusOptions}
            required
          />
        </div>

        {/* 7 & 8. Start Date & Due Date */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Input
            label="7. Start Date"
            id="task-start-date"
            type="date"
            value={formData.startDate}
            onChange={(e) => handleChange('startDate', e.target.value)}
            required
            error={errors.startDate}
          />

          <Input
            label="8. Due Date"
            id="task-due-date"
            type="date"
            value={formData.dueDate}
            onChange={(e) => handleChange('dueDate', e.target.value)}
            required
            error={errors.dueDate}
          />
        </div>

        {/* 9. Associated Goal (Optional) */}
        <div>
          <Select
            label="9. Associated Goal (Optional)"
            id="task-associated-goal"
            value={formData.associatedGoalId}
            onChange={(e) => handleChange('associatedGoalId', e.target.value)}
            options={goalOptions}
            helperText="Link this task to an existing short-term or long-term goal"
          />
        </div>
      </form>
    </Modal>
  );
}
