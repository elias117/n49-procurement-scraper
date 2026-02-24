output "instance_id" {
  description = "EC2 instance ID"
  value       = aws_instance.app.id
}

output "public_ip" {
  description = "Elastic IP address"
  value       = aws_eip.app.public_ip
}

output "ssh_command" {
  description = "SSH command to connect to the instance"
  value       = "ssh -i terraform/${var.project_name}-key.pem ec2-user@${aws_eip.app.public_ip}"
}

output "domain" {
  description = "Application domain"
  value       = var.domain_name
}

output "ssh_key_path" {
  description = "Path to SSH private key"
  value       = local_file.ssh_private_key.filename
  sensitive   = true
}
