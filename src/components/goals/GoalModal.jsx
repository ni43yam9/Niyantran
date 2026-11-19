import { useState, useEffect } from 'react';
import { Modal } from '../common/Modal';
import { Button } from '../common/Button';
import { Input, Textarea, Select } from '../common/FormControls';
import { useApp } from '../../context/AppContext';
import { GOAL_TYPES } from '../../constants/theme';
import { getTodayString } from '../../utils/dateUtils';

const getDefaultGoalForm = () => {
  const today = getTodayString();
  const d = new Date();
  d.setDate(d.getDate() + 60);
  const targetDefault = d.toISOString().split('T')[0];

  return {
    title: '',
    description: '',
    type: 'Short-Term',
    category: 'Coding',
    priority: 'High',
    status: 'In Progress',
    startDate: today,
    targetDate: targetDefault,
    progress: 0,
    keyMilestone: '',
  };
};

export function GoalModal({ isOpen, onClose, editingGoal }) {
  const { addGoal, updateGoal } = useApp();

  const [formData, setFormData] = useState(getDefaultGoalForm);

  const [errors, setErrors] = useState({});

  useEffect(() => {
    if (editingGoal) {
      setFormData({
        title: editingGoal.title || '',
        description: editingGoal.description || '',
        type: editingGoal.type || 'Short-Term',
        category: editingGoal.category || 'Coding',
        priority: editingGoal.priority || 'High',
        status: editingGoal.status || 'In Progress',
        startDate: editingGoal.startDate || getTodayString(),
        targetDate: editingGoal.targetDate || '',
        progress: editingGoal.progress || 0,
        keyMilestone: editingGoal.keyMilestone || '',
      });
    } else {
      setFormData(getDefaultGoalForm());
    }
    setErrors({});
  }, [editingGoal, isOpen]);

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
      newErrors.title = 'Goal title is required';
    } else if (formData.title.trim().length > 140) {
      newErrors.title = 'Goal title must be 140 characters or fewer';
    }

    if (!formData.startDate) {
      newErrors.startDate = 'Start date is required';
    }
    if (!formData.targetDate) {
      newErrors.targetDate = 'Target completion date is required';
    } else if (formData.startDate && formData.targetDate < formData.startDate) {
      newErrors.targetDate = 'Target completion date cannot be earlier than start date';
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    if (editingGoal) {
      updateGoal({ ...editingGoal, ...formData });
    } else {
      addGoal(formData);
    }
  };

  const categoryOptions = [
    { value: 'Coding', label: 'Coding & Tech' },
    { value: 'Academic', label: 'Academic & Coursework' },
    { value: 'Career', label: 'Career & Internship' },
    { value: 'Technical', label: 'Technical Mastery' },
    { value: 'Personal', label: 'Personal & Lifestyle' },
    { value: 'Health', label: 'Health & Fitness' },
  ];

  const priorityOptions = [
    { value: 'High', label: 'High Priority' },
    { value: 'Medium', label: 'Medium Priority' },
    { value: 'Low', label: 'Low Priority' },
  ];

  const statusOptions = [
    { value: 'In Progress', label: 'In Progress' },
    { value: 'On Track', label: 'On Track' },
    { value: 'Behind', label: 'Behind Schedule' },
    { value: 'Completed', label: 'Completed' },
  ];

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={editingGoal ? 'Edit Goal' : 'Create New Goal'}
      subtitle={
        editingGoal
          ? 'Update your milestone roadmap and completion metrics'
          : 'Set a high-impact academic, technical, or personal benchmark'
      }
      size="lg"
      footer={
        <>
          <Button variant="outline" size="md" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" size="md" onClick={handleSubmit}>
            {editingGoal ? 'Save Goal' : 'Create Goal'}
          </Button>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* 1. Title */}
        <Input
          label="1. Goal Title"
          id="goal-title"
          placeholder="e.g., Solve 100 DSA Problems / Secure Top Research Internship"
          value={formData.title}
          onChange={(e) => handleChange('title', e.target.value)}
          required
          error={errors.title}
        />

        {/* 2. Description */}
        <Textarea
          label="2. Description & Vision"
          id="goal-description"
          placeholder="Outline what success looks like, core competencies, and required outcomes..."
          value={formData.description}
          onChange={(e) => handleChange('description', e.target.value)}
          rows={3}
        />

        {/* 3 & 4. Goal Type & Category */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Select
            label="3. Goal Horizon / Type"
            id="goal-type"
            value={formData.type}
            onChange={(e) => handleChange('type', e.target.value)}
            options={GOAL_TYPES.map((g) => ({ value: g.id, label: g.label }))}
            required
            helperText="Short-term (weeks/months) or Long-term (strategic vision)"
          />

          <Select
            label="4. Domain / Category"
            id="goal-category"
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
            id="goal-priority"
            value={formData.priority}
            onChange={(e) => handleChange('priority', e.target.value)}
            options={priorityOptions}
            required
          />

          <Select
            label="6. Status"
            id="goal-status"
            value={formData.status}
            onChange={(e) => handleChange('status', e.target.value)}
            options={statusOptions}
            required
          />
        </div>

        {/* 7 & 8. Start Date & Target Completion Date */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Input
            label="7. Start Date"
            id="goal-start-date"
            type="date"
            value={formData.startDate}
            onChange={(e) => handleChange('startDate', e.target.value)}
            required
            error={errors.startDate}
          />

          <Input
            label="8. Target Completion Date"
            id="goal-target-date"
            type="date"
            value={formData.targetDate}
            onChange={(e) => handleChange('targetDate', e.target.value)}
            required
            error={errors.targetDate}
          />
        </div>

        {/* Key Milestone / Target metric */}
        <div>
          <Input
            label="Key Milestone / Deliverable"
            id="goal-milestone"
            placeholder="e.g., Publish 2 end-to-end open source ML pipelines"
            value={formData.keyMilestone}
            onChange={(e) => handleChange('keyMilestone', e.target.value)}
            helperText="Crucial checkpoint to evaluate progress"
          />
        </div>
      </form>
    </Modal>
  );
}
