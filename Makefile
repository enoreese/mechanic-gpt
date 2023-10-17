ifneq (,$(wildcard ./.env))
    include .env
	# assume includes MODAL_TOKEN_ID and MODAL_TOKEN_SECRET for modal auth,
	# assume includes DISCORD_AUTH for running discord bot,
	# assume includes MONGODB_URI and MONGODB_PASSWORD for document store setup
    export
endif

.PHONY: help
.DEFAULT_GOAL := help

help: ## get a list of all the targets, and their short descriptions
	@# source for the incantation: https://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' Makefile | awk 'BEGIN {FS = ":.*?##"}; {printf "\033[36m%-12s\033[0m %s\n", $$1, $$2}'

edmunds_store: modal_auth ## Scrape edmunds Repairs and Maintenance forum
	@echo "###"
	@echo "# 🥞: Assumes you've set up a GCP connection and secret"
	@echo "###"
	modal run scraper/scrape_edmunds.py::stub.main

modal_auth: environment ## confirms authentication with Modal, using secrets from `.env` file
	@echo "###"
	@echo "# 🥞: If you haven't gotten a Modal token yet, run make modal_token"
	@echo "###"
	@modal token set --token-id $(MODAL_TOKEN_ID) --token-secret $(MODAL_TOKEN_SECRET)

modal_token: environment ## creates token ID and secret for authentication with modal
	modal token new
	@echo "###"
	@echo "# 🥞: Copy the token info from the file mentioned above into .env"
	@echo "###"

environment: ## installs required environment for deployment
	pip install -qqq -r requirements.txt

dev_environment:  ## installs required environment for development & document corpus generation
	pip install -qqq -r requirements-dev.txt