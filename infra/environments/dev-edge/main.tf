provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "Integration Catalogue"
      Environment = "DEV"
      ManagedBy   = "Terraform"
      Layer       = "Edge"
    }
  }
}

data "aws_cloudfront_cache_policy" "caching_disabled" {
  name = "Managed-CachingDisabled"
}

data "aws_cloudfront_origin_request_policy" "all_viewer" {
  name = "Managed-AllViewer"
}

data "aws_cloudfront_response_headers_policy" "security_headers" {
  name = "Managed-SecurityHeadersPolicy"
}

resource "aws_cloudfront_function" "lifecycle" {
  name    = "integration-catalogue-dev-lifecycle"
  runtime = "cloudfront-js-2.0"
  comment = "Integration Catalogue DEV active or maintenance state"
  publish = true
  code = templatefile("${path.module}/lifecycle.js.tftpl", {
    maintenance_mode = jsonencode(var.maintenance_mode)
  })
}

resource "aws_cloudfront_distribution" "dev" {
  enabled         = true
  is_ipv6_enabled = true
  comment         = "integration-catalogue-dev-${var.maintenance_mode ? "maintenance" : "active"}"
  price_class     = "PriceClass_100"

  origin {
    domain_name = var.origin_domain_name
    origin_id   = "integration-catalogue-dev-runtime"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  default_cache_behavior {
    target_origin_id       = "integration-catalogue-dev-runtime"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true

    cache_policy_id            = data.aws_cloudfront_cache_policy.caching_disabled.id
    origin_request_policy_id   = data.aws_cloudfront_origin_request_policy.all_viewer.id
    response_headers_policy_id = data.aws_cloudfront_response_headers_policy.security_headers.id

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.lifecycle.arn
    }
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  wait_for_deployment = true
}

