output "codebuild_project_name" {
  description = "CodeBuild project used by both manual and scheduled DEV lifecycle requests."
  value       = aws_codebuild_project.lifecycle.name
}

output "image_parameter_name" {
  description = "SSM parameter retaining the last successfully selected DEV image tag."
  value       = aws_ssm_parameter.image_tag.name
}

output "activate_schedule" {
  description = "Weekday activation schedule and timezone."
  value = {
    expression = aws_scheduler_schedule.activate.schedule_expression
    timezone   = aws_scheduler_schedule.activate.schedule_expression_timezone
    state      = aws_scheduler_schedule.activate.state
  }
}

output "maintain_schedule" {
  description = "Weekday maintenance schedule and timezone."
  value = {
    expression = aws_scheduler_schedule.maintain.schedule_expression
    timezone   = aws_scheduler_schedule.maintain.schedule_expression_timezone
    state      = aws_scheduler_schedule.maintain.state
  }
}
