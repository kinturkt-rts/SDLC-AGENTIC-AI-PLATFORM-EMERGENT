terraform {
  required_version = ">= 1.10"
  backend "s3" {
    bucket       = "sdlc-tfstate-061836593297-us-east-2"
    key          = "dev/apps/meeting-assistant/terraform.tfstate"
    region       = "us-east-2"
    use_lockfile = true
  }
}
