# ————— OS Detection ————— #
ifeq ($(OS),Windows_NT)
    PYTHON = py -3
    VENV_PY = venv/Scripts/python.exe
else
    PYTHON = python3
    VENV_PY = venv/bin/python3
endif

# ————— Colour Definitions ————— #
GREEN  = \033[32m
YELLOW = \033[33m
RED    = \033[31m
BLUE   = \033[34m
RESET  = \033[0m



# ————— Main Calls ————— #
# Create the python server
run: install
	@echo -e "$(BLUE)Starting server...$(RESET)"
	@$(VENV_PY) Model/testserver.py




# ————— Virtual Environment Creation ————— #
# Create the virtual environment
venv:
	@echo -e "$(BLUE)Creating virtual environment...$(RESET)"
	@$(PYTHON) -m venv venv
	@echo -e "$(GREEN)Environment created.$(RESET)"

# Install needed dependencies to the virtual environment
requirements:
	@echo -e "$(BLUE)Installing required packages...$(RESET)"
	@$(VENV_PY) -m pip install --upgrade pip
	@$(VENV_PY) -m pip install -r requirements.txt
	@echo -e "$(GREEN)Install complete.$(RESET)"

# main installation call
install: venv requirements
	@echo -e "$(GREEN)Installation complete.$(RESET)"

# ————— Cleanup ————— #
clean:
	@echo -e "$(YELLOW)Removing virtual environment...$(RESET)"
	@rm -rf venv
	@echo -e "$(YELLOW)Removing log files...$(RESET)"
	@rm -f *.log
	@echo -e "$(GREEN)Clean complete.$(RESET)"