// Copyright (c) 2026 Xavier Callens / Socrate AI Lab
// Licensed under Apache 2.0 - see LICENSE file

//! # Task Scheduler Interface
//!
//! Abstract task scheduler interface for RunuX kernel deployment on
//! RISC-V and ARM architectures. Provides priority-based task
//! scheduling with preemption support.
//!
//! ## Architecture Support
//!
//! - **RISC-V** — RV64GC with vector extension (V 1.0)
//! - **ARM** — ARMv8-A with NEON SIMD and SVE
//!
//! In simulation mode (non-bare-metal), tasks are dispatched through
//! Tokio's async runtime.

use serde::{Deserialize, Serialize};
use thiserror::Error;
use std::time::Duration;

/// Errors from the scheduler.
#[derive(Debug, Error)]
pub enum SchedulerError {
    /// Task queue is full.
    #[error("task queue full: {max_tasks} tasks")]
    QueueFull { max_tasks: usize },

    /// Task was not found.
    #[error("task {0} not found")]
    TaskNotFound(u64),

    /// Task execution timed out.
    #[error("task {id} timed out after {timeout:?}")]
    Timeout { id: u64, timeout: Duration },

    /// Invalid priority level.
    #[error("invalid priority: {0}")]
    InvalidPriority(u8),
}

/// Task priority levels.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
pub enum TaskPriority {
    /// Idle — lowest priority, runs when nothing else is scheduled.
    Idle = 0,
    /// Background — batch processing, model loading.
    Background = 1,
    /// Normal — standard inference tasks.
    Normal = 2,
    /// High — time-sensitive reasoning steps.
    High = 3,
    /// Critical — safety-critical verification, proof checking.
    Critical = 4,
}

impl TaskPriority {
    /// Converts a raw u8 to a priority level.
    ///
    /// # Errors
    ///
    /// Returns [`SchedulerError::InvalidPriority`] for values > 4.
    pub fn from_u8(value: u8) -> Result<Self, SchedulerError> {
        match value {
            0 => Ok(Self::Idle),
            1 => Ok(Self::Background),
            2 => Ok(Self::Normal),
            3 => Ok(Self::High),
            4 => Ok(Self::Critical),
            _ => Err(SchedulerError::InvalidPriority(value)),
        }
    }
}

/// Target CPU architecture.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum CpuArchitecture {
    /// RISC-V 64-bit with general + compressed + vector extensions.
    RiscV64GCV,
    /// ARM v8-A with NEON.
    AArch64Neon,
    /// ARM v8-A with SVE.
    AArch64Sve,
    /// x86-64 with AVX2 (simulation/development).
    X86_64Avx2,
    /// Generic (no SIMD).
    Generic,
}

/// Scheduler configuration.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SchedulerConfig {
    /// Maximum number of concurrent tasks.
    pub max_tasks: usize,
    /// Default task timeout.
    pub default_timeout: Duration,
    /// Target CPU architecture.
    pub architecture: CpuArchitecture,
    /// Whether to enable preemptive scheduling.
    pub preemptive: bool,
    /// Time quantum for round-robin (when preemptive).
    pub time_quantum: Duration,
}

impl Default for SchedulerConfig {
    fn default() -> Self {
        Self {
            max_tasks: 256,
            default_timeout: Duration::from_secs(30),
            architecture: CpuArchitecture::Generic,
            preemptive: false,
            time_quantum: Duration::from_millis(10),
        }
    }
}

/// State of a scheduled task.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum TaskState {
    /// Task is queued but not yet running.
    Pending,
    /// Task is currently executing.
    Running,
    /// Task completed successfully.
    Completed,
    /// Task failed with an error.
    Failed,
    /// Task was cancelled.
    Cancelled,
    /// Task timed out.
    TimedOut,
}

/// A scheduled task descriptor.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskDescriptor {
    /// Unique task ID.
    pub id: u64,
    /// Human-readable task name.
    pub name: String,
    /// Task priority.
    pub priority: TaskPriority,
    /// Task state.
    pub state: TaskState,
    /// Task timeout override (None = use default).
    pub timeout: Option<Duration>,
}

/// Task scheduler for RunuX kernel deployment.
///
/// Manages task queuing, priority-based scheduling, and preemption
/// for SymBrain inference workloads on edge devices.
#[derive(Debug)]
pub struct TaskScheduler {
    /// Configuration.
    config: SchedulerConfig,
    /// Task queue.
    tasks: Vec<TaskDescriptor>,
    /// Next task ID.
    next_id: u64,
    /// Total tasks completed.
    completed: u64,
}

impl TaskScheduler {
    /// Creates a new task scheduler with the given configuration.
    pub fn new(config: SchedulerConfig) -> Self {
        Self {
            tasks: Vec::with_capacity(config.max_tasks),
            config,
            next_id: 1,
            completed: 0,
        }
    }

    /// Submits a task to the scheduler.
    ///
    /// # Errors
    ///
    /// Returns [`SchedulerError::QueueFull`] if the queue is at capacity.
    pub fn submit(
        &mut self,
        name: impl Into<String>,
        priority: TaskPriority,
        timeout: Option<Duration>,
    ) -> Result<u64, SchedulerError> {
        if self.tasks.len() >= self.config.max_tasks {
            return Err(SchedulerError::QueueFull {
                max_tasks: self.config.max_tasks,
            });
        }

        let id = self.next_id;
        self.next_id += 1;

        let task = TaskDescriptor {
            id,
            name: name.into(),
            priority,
            state: TaskState::Pending,
            timeout,
        };

        // Insert in priority order (higher priority first)
        let insert_pos = self
            .tasks
            .iter()
            .position(|t| t.priority < priority)
            .unwrap_or(self.tasks.len());
        self.tasks.insert(insert_pos, task);

        tracing::debug!(task_id = id, ?priority, "task submitted");

        Ok(id)
    }

    /// Polls the next task to execute (highest priority pending task).
    pub fn poll_next(&mut self) -> Option<&mut TaskDescriptor> {
        self.tasks
            .iter_mut()
            .find(|t| t.state == TaskState::Pending)
    }

    /// Marks a task as completed.
    ///
    /// # Errors
    ///
    /// Returns [`SchedulerError::TaskNotFound`] if the task ID is invalid.
    pub fn complete(&mut self, task_id: u64) -> Result<(), SchedulerError> {
        let task = self
            .tasks
            .iter_mut()
            .find(|t| t.id == task_id)
            .ok_or(SchedulerError::TaskNotFound(task_id))?;
        task.state = TaskState::Completed;
        self.completed += 1;
        Ok(())
    }

    /// Cancels a pending task.
    ///
    /// # Errors
    ///
    /// Returns [`SchedulerError::TaskNotFound`] if the task ID is invalid.
    pub fn cancel(&mut self, task_id: u64) -> Result<(), SchedulerError> {
        let task = self
            .tasks
            .iter_mut()
            .find(|t| t.id == task_id)
            .ok_or(SchedulerError::TaskNotFound(task_id))?;
        task.state = TaskState::Cancelled;
        Ok(())
    }

    /// Returns the number of pending tasks.
    pub fn pending_count(&self) -> usize {
        self.tasks
            .iter()
            .filter(|t| t.state == TaskState::Pending)
            .count()
    }

    /// Returns the number of running tasks.
    pub fn running_count(&self) -> usize {
        self.tasks
            .iter()
            .filter(|t| t.state == TaskState::Running)
            .count()
    }

    /// Returns the total number of completed tasks.
    pub fn completed_count(&self) -> u64 {
        self.completed
    }

    /// Removes completed/cancelled tasks from the queue.
    pub fn gc(&mut self) {
        self.tasks.retain(|t| {
            t.state == TaskState::Pending || t.state == TaskState::Running
        });
    }

    /// Returns the scheduler configuration.
    pub fn config(&self) -> &SchedulerConfig {
        &self.config
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_submit_and_poll() {
        let mut sched = TaskScheduler::new(SchedulerConfig::default());
        let id = sched.submit("test_task", TaskPriority::Normal, None).unwrap();
        assert_eq!(sched.pending_count(), 1);

        let task = sched.poll_next().unwrap();
        assert_eq!(task.id, id);
    }

    #[test]
    fn test_priority_ordering() {
        let mut sched = TaskScheduler::new(SchedulerConfig::default());
        sched.submit("low", TaskPriority::Idle, None).unwrap();
        sched.submit("high", TaskPriority::Critical, None).unwrap();
        sched.submit("mid", TaskPriority::Normal, None).unwrap();

        let next = sched.poll_next().unwrap();
        assert_eq!(next.priority, TaskPriority::Critical);
    }

    #[test]
    fn test_queue_full() {
        let config = SchedulerConfig {
            max_tasks: 2,
            ..Default::default()
        };
        let mut sched = TaskScheduler::new(config);
        sched.submit("t1", TaskPriority::Normal, None).unwrap();
        sched.submit("t2", TaskPriority::Normal, None).unwrap();
        assert!(sched.submit("t3", TaskPriority::Normal, None).is_err());
    }

    #[test]
    fn test_complete_and_gc() {
        let mut sched = TaskScheduler::new(SchedulerConfig::default());
        let id = sched.submit("task", TaskPriority::Normal, None).unwrap();
        sched.complete(id).unwrap();
        assert_eq!(sched.completed_count(), 1);
        sched.gc();
        assert_eq!(sched.pending_count(), 0);
    }
}
