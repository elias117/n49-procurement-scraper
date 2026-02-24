variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "ca-central-1"
}

variable "project_name" {
  description = "Project name used for resource tagging"
  type        = string
  default     = "procurement-intel"
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.large"
}

variable "domain_name" {
  description = "Domain name for the application"
  type        = string
  default     = "procurement.eliastools.com"
}

variable "root_domain" {
  description = "Root domain for Route53 zone lookup"
  type        = string
  default     = "eliastools.com"
}

variable "ssh_allowed_cidr" {
  description = "CIDR block allowed to SSH (set to your IP/32 for security)"
  type        = string
  default     = "0.0.0.0/0"
}
