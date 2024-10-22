import argparse
import os
from pathlib import Path
import shutil
import subprocess
import json

cwd = Path.cwd()
project = None


def run_command(cmd: str, **kwargs):
    """Helper function to run shell commands."""
    subprocess.run(cmd.split(" "), **kwargs)


def update_cross_compile(makefile_path, new_path):
    """
    Updates the CROSS_COMPILE variable in a Makefile to a new path.

    Parameters:
    makefile_path (str): Path to the Makefile.
    new_path (str): The new path to set for CROSS_COMPILE.

    Returns:
    bool: True if the update was successful, False otherwise.
    """
    try:
        # Read the contents of the Makefile
        with open(makefile_path, "r") as file:
            lines = file.readlines()

        # Initialize a flag to check if CROSS_COMPILE was found
        cross_compile_found = False

        # Iterate through the lines to find and update CROSS_COMPILE
        for i in range(len(lines)):
            if lines[i].startswith("CROSS_COMPILE"):
                lines[i] = f"CROSS_COMPILE = {new_path}\n"
                cross_compile_found = True
                break

        # If CROSS_COMPILE was not found, add it at the end
        if not cross_compile_found:
            lines.append(f"\nCROSS_COMPILE = {new_path}\n")

        # Write the updated contents back to the Makefile
        with open(makefile_path, "w") as file:
            file.writelines(lines)

        return True

    except Exception as e:
        print(f"Error: {e}")
        return False


def download_compiler(path: Path):
    """Download and extract the ARM compiler."""
    run_command(
        "curl -o compiler.tar.bz2 https://armkeil.blob.core.windows.net/developer/Files/downloads/gnu-rm/10.3-2021.07/gcc-arm-none-eabi-10.3-2021.07-mac-10.14.6.tar.bz2",
        cwd=path,
    )
    run_command("tar -xvf compiler.tar.bz2", cwd=path)


def update_path_for_compiler(path: Path):
    """Update the PATH variable to include the ARM compiler."""
    home_directory = os.path.expanduser("~")
    zshrc_path = os.path.join(home_directory, ".zshrc")
    compiler_path = path / "gcc-arm-none-eabi-10.3-2021.07" / "bin"
    with open(zshrc_path, "a") as f:
        f.write(f'\nexport PATH="{compiler_path}:$PATH"\n')
        print("Compiler added to PATH")
    print("Please run 'source ~/.zshrc' to update the PATH in the current shell.")


def install_compiler(path: Path):
    """Install ARM compiler if not already installed."""
    compiler = path / "gcc-arm-none-eabi-10.3-2021.07"
    if compiler.exists():
        print("Compiler already exists")
    else:
        download_compiler(path)


def install_stlink():
    """Install stlink using Homebrew."""
    run_command("brew install stlink")


def get_micropython(path: Path):
    """Clone the MicroPython repository, switch to a specific branch, and set up submodules."""
    run_command(
        "git clone --recurse-submodules https://github.com/micropython/micropython.git",
        cwd=path,
    )
    # Switch to the v1.22-release branch
    run_command("git checkout v1.22-release", cwd=path / "micropython")
    
    run_command("git submodule update --init", cwd=path / "micropython")
    run_command("mkdir modules", cwd=path / "micropython/ports/stm32")
    manifest = path / "micropython/ports/stm32/boards/NUCLEO_H743ZI/manifest.py"
    with open(manifest, "a") as f:
        f.write('freeze("$(PORT_DIR)/modules/app")')



def compile_firmware():
    """Compile the firmware for MicroPython."""
    run_command("make -C mpy-cross", cwd=cwd / "stm32/micropython")
    run_command("make submodules", cwd=cwd / "stm32/micropython/ports/stm32")

    # Remove existing app directory if it exists
    app_path = cwd / "stm32/micropython/ports/stm32/modules/app"
    if app_path.exists():
        shutil.rmtree(app_path)

    shutil.copytree(cwd / "app", app_path)
    run_command("make BOARD=NUCLEO_H743ZI", cwd=cwd / "stm32/micropython/ports/stm32")


def flash_firmware():
    """Flash the firmware to the board."""
    run_command(
        "st-flash --connect-under-reset --format ihex write build-NUCLEO_H743ZI/firmware.hex",
        cwd=cwd / "stm32/micropython/ports/stm32",
    )


def reset_device():
    """Reset the connected device."""
    run_command("st-flash --connect-under-reset reset")


def clean_build():
    """Clean the build directory for MicroPython."""
    run_command("make clean", cwd=cwd / "stm32/micropython/ports/stm32")


def setup_stm32_project(delete_current: bool):
    """Setup a new project for developing on STM32."""

    project_path = cwd

    if delete_current:
        confirmation = input(
            f"Do you want to delete this project and recreate it? (y/n): "
        ).lower()
        if confirmation == "y":
            for item in project_path.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
            print("Deleted existing project content.")
        else:
            print("Setup aborted.")
            return
    else:
        project_name = input("Enter the name of your new STM32 project: ")
        project_path = cwd / project_name
        project_path.mkdir(parents=True, exist_ok=True)

    # Step 1: Create new project folder structure
    stm32_path = project_path / "stm32"
    arm_gcc_compiler_path = stm32_path / "arm_gcc_compiler"
    micropython_path = stm32_path / "micropython"
    app_path = project_path / "app"
    vscode_path = project_path / ".vscode"
    vscode_tasks_path = vscode_path / "tasks.json"
    setup_script_path = stm32_path / "setup.py"

    stm32_path.mkdir(parents=True, exist_ok=True)
    arm_gcc_compiler_path.mkdir(parents=True, exist_ok=True)
    app_path.mkdir(parents=True, exist_ok=True)
    with open(app_path / "app.py", "w") as f:
        f.write(
            """
import pyb

def run():
    print("run function is runing")
    pyb.LED(1).on()
"""
        )
    vscode_path.mkdir(parents=True, exist_ok=True)

    # Install compiler
    install_compiler(arm_gcc_compiler_path)

    # Step 2: Clone the MicroPython repository
    get_micropython(stm32_path)
    update_cross_compile(
        cwd / project_name / "stm32/micropython/ports/stm32/Makefile",
        cwd
        / project_name
        / "stm32/arm_gcc_compiler/gcc-arm-none-eabi-10.3-2021.07/bin/arm-none-eabi-",
    )

    # Step 3: Copy the current script to setup.py
    shutil.copy(__file__, setup_script_path)
    print(f"Setup script copied to {setup_script_path}")

    # Step 4: Create tasks.json for VSCode
    tasks_content = {
        "version": "2.0.0",
        "tasks": [
            {
                "label": "Setup",
                "type": "shell",
                "command": "python3 stm32/setup.py setup",
            },
            {
                "label": "Compile",
                "type": "shell",
                "command": "python3 stm32/setup.py compile",
            },
            {
                "label": "Flash",
                "type": "shell",
                "command": "python3 stm32/setup.py flash",
                "dependsOn": "Compile",
            },
            {
                "label": "Reset",
                "type": "shell",
                "command": "python3 stm32/setup.py reset",
            },
        ],
    }
    vscode_tasks_path.write_text(json.dumps(tasks_content, indent=4))
    print(f"VSCode tasks.json created at {vscode_tasks_path}")

    # Step 5: Install stlink
    install_stlink()

    print(f"STM32 project setup completed at {project_path}")


def main():
    parser = argparse.ArgumentParser(description="A simple CLI program.")
    subparsers = parser.add_subparsers(dest="command")

    # Define all the subcommands
    subparsers.add_parser("stlink", help="install stlink")
    subparsers.add_parser("compiler", help="install compiler arm_none_eabi_gcc")
    subparsers.add_parser("compile", help="compile the firmware")
    subparsers.add_parser("flash", help="flash the firmware to the board")
    subparsers.add_parser("reset", help="reset the connected device")
    subparsers.add_parser("get_mpy", help="clone and setup micropython")
    subparsers.add_parser("clean", help="clean the build directory")
    setup_parser = subparsers.add_parser(
        "setup", help="setup a new STM32 project environment"
    )
    setup_parser.add_argument("--delete_current", action="store_true")
    args = parser.parse_args()

    # Mapping commands to functions
    command_mapping = {
        "compiler": lambda: install_compiler(cwd / "stm32" / "arm_gcc_compiler"),
        "get_mpy": lambda: get_micropython(cwd / "stm32"),
        "stlink": install_stlink,
        "compile": compile_firmware,
        "flash": flash_firmware,
        "reset": reset_device,
        "clean": clean_build,
        "setup": lambda: setup_stm32_project(args.delete_current),
    }

    if args.command in command_mapping:
        command_mapping[args.command]()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
