# Rich library imports for terminal styling and formatting
from rich.console import Console  # Main class for styled terminal output
from rich.table import Table     # For creating styled tables
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn  # Progress bar components
from rich.live import Live       # For live-updating displays
from rich.style import Style     # For custom styling rules

# Standard library imports
import subprocess
import json
import datetime
import os
import inquirer  # For interactive CLI prompts
import sys
import glob
import time
from packaging.requirements import Requirement
from concurrent.futures import ThreadPoolExecutor, as_completed

def find_requirements_files():
    """Find all requirements files in current directory."""
    patterns = ['*requirements*.txt', '*requirements*.pip']
    requirements_files = []
    for pattern in patterns:
        requirements_files.extend(glob.glob(pattern))
    return requirements_files

def parse_requirements_file(file_path):
    """Parse a requirements file and return list of package requirements."""
    try:
        with open(file_path, 'r') as f:
            return [Requirement(line.strip()) 
                   for line in f 
                   if line.strip() and not line.startswith('#')]
    except Exception as e:
        print(f"\nError reading requirements file: {e}")
        return []

def run_pip_command(command, args, global_packages=True):
    """Execute a pip command and return its output."""
    try:
        cmd = [sys.executable, '-m', 'pip'] + command
        if not global_packages:
            cmd.append('--user')
        cmd.extend(args)
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"\nError executing pip command: {e.stderr}")
        return None

def get_package_description(package_name):
    """Get description for a single package using pip show."""
    output = run_pip_command(['show'], [package_name])
    if output:
        for line in output.split('\n'):
            if line.startswith('Summary: '):
                return line[9:].strip()
    return "No description available"

def get_package_descriptions_parallel(packages, max_workers=10):
    """Get package descriptions in parallel using ThreadPoolExecutor.
    
    This is an optimization that fetches multiple package descriptions concurrently,
    significantly reducing the time needed for large numbers of packages.
    """
    descriptions = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_package = {
            executor.submit(get_package_description, package['name']): package['name']
            for package in packages
        }
        for future in as_completed(future_to_package):
            package_name = future_to_package[future]
            try:
                descriptions[package_name] = future.result()
            except Exception:
                descriptions[package_name] = "No description available"
    return descriptions

def get_all_packages(global_packages=True):
    """Get list of all installed packages with their descriptions."""
    output = run_pip_command(['list'], ['--format=json'], global_packages)
    if output:
        try:
            packages = json.loads(output)
            # Get descriptions in parallel for better performance
            descriptions = get_package_descriptions_parallel(packages)
            for package in packages:
                package['description'] = descriptions.get(package['name'], "No description available")
            return packages
        except json.JSONDecodeError:
            print("\nError: Failed to parse package information")
            return []
    return []

def get_outdated_packages(global_packages=True):
    """Get list of outdated packages."""
    output = run_pip_command(['list', '--outdated'], ['--format=json'], global_packages)
    if output:
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            print("\nError: Failed to parse outdated package information")
            return []
    return []

def create_backup(packages):
    """Create a backup of current package versions."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = "package_backups"
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    
    backup_file = os.path.join(backup_dir, f"package_versions_{timestamp}.json")
    
    if packages:
        try:
            with open(backup_file, 'w') as f:
                json.dump(packages, f, indent=4)
            return backup_file
        except IOError as e:
            print(f"\nError creating backup: {e}")
            return None
    return None

def update_packages(outdated_packages, console, global_packages=True):
    """Update outdated packages with progress bar."""
    # Create a progress bar with spinner, text description, progress bar, and elapsed time
    with Progress(
        SpinnerColumn(),          # Animated spinner
        TextColumn("[progress.description]{task.description}"),  # Description text
        BarColumn(),              # Progress bar
        TimeElapsedColumn(),      # Elapsed time
        console=console,
    ) as progress:
        task = progress.add_task("Updating packages...", total=len(outdated_packages))
        for package in outdated_packages:
            name = package['name']
            version = package['latest_version']
            result = run_pip_command(['install', '--upgrade'], [f"{name}=={version}"], global_packages)
            if result is None:
                progress.update(task, description=f"Failed to update {name}")
            else:
                progress.update(task, advance=1)

def restore_packages(backup_file, console):
    """Restore packages from a backup file with progress bar."""
    try:
        with open(backup_file, 'r') as f:
            packages = json.loads(f.read())
    except (IOError, json.JSONDecodeError) as e:
        print(f"\nError reading backup file: {e}")
        return False
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Restoring packages...", total=len(packages))
        for package in packages:
            name = package['name']
            version = package['version']
            result = run_pip_command(['install'], [f"{name}=={version}"])
            if result is None:
                progress.update(task, description=f"Failed to restore {name}")
            else:
                progress.update(task, advance=1)
    
    return True

def display_version_table(console, all_packages, outdated_map):
    """Display a formatted table of package versions with styling.
    
    Styling Features:
    - Table headers with yellow style for package name and latest version
    - Outdated packages highlighted with bright cyan background
    - Status column with colored text (red for outdated, green for up to date)
    - Sorted display with outdated packages shown first
    """
    if not all_packages:
        console.print("\n[red]No package information available[/red]")
        return
    
    # Create table with styled headers
    table = Table(show_header=True)
    table.add_column("Package Name", style="yellow")      # Yellow style for package names
    table.add_column("Current Version")
    table.add_column("Latest Version", style="yellow")    # Yellow style for latest version
    table.add_column("Status", style="bold")              # Bold style for status
    table.add_column("Description")
    
    # Sort packages and separate outdated from up-to-date
    sorted_packages = sorted(all_packages, key=lambda x: x['name'].lower())
    outdated_packages = [pkg for pkg in sorted_packages if pkg['name'] in outdated_map]
    uptodate_packages = [pkg for pkg in sorted_packages if pkg['name'] not in outdated_map]
    
    # Add outdated packages first with highlight styling
    for package in outdated_packages:
        name = package['name']
        current = package['version']
        description = package.get('description', "No description available")
        latest = outdated_map[name]['latest_version']
        status = "[red]Outdated[/red]"  # Red text for outdated status
        
        # Style outdated packages with bright cyan background
        styled_name = f"[black on bright_cyan]{name}[/]"
        styled_current = f"[black on bright_cyan]{current}[/]"
        styled_latest = f"[black on bright_cyan]{latest}[/]"
        styled_status = f"[black on bright_cyan]{status}[/]"
        table.add_row(styled_name, styled_current, styled_latest, styled_status, description)
    
    # Add up-to-date packages
    for package in uptodate_packages:
        name = package['name']
        current = package['version']
        description = package.get('description', "No description available")
        status = "[green]Up to date[/green]"  # Green text for up-to-date status
        table.add_row(name, current, current, status, description)
    
    console.print(table)

def check_project_packages(console, requirements_file):
    """Check status of packages in a requirements file."""
    console.print(f"\n[bold blue]Checking packages from {requirements_file}[/bold blue]")
    required_packages = parse_requirements_file(requirements_file)
    required_names = {pkg.name for pkg in required_packages}
    
    # Analysis progress messages with timing
    console.print("Analyzing project dependencies...")
    start_time = time.time()
    all_installed = get_all_packages(global_packages=False)
    analysis_time = time.time() - start_time
    console.print(f"Analysis completed in {analysis_time:.2f}s")
    
    console.print("Checking for updates...")
    start_time = time.time()
    outdated = get_outdated_packages(global_packages=False)
    update_check_time = time.time() - start_time
    console.print(f"Updates check completed in {update_check_time:.2f}s")
    
    # Filter packages to only those in requirements file
    project_packages = [
        pkg for pkg in all_installed
        if pkg['name'].lower() in {name.lower() for name in required_names}
    ]
    
    # Filter outdated packages to only those in requirements
    project_outdated = [
        pkg for pkg in outdated
        if pkg['name'].lower() in {name.lower() for name in required_names}
    ]
    
    if not project_packages:
        console.print("\n[red]No matching packages found in requirements file[/red]")
        return
    
    outdated_map = {pkg['name']: pkg for pkg in project_outdated}
    
    # Display current state
    console.print("\n[bold]Project Package Status:[/bold]")
    display_version_table(console, project_packages, outdated_map)
    
    return project_packages, project_outdated

def check_global_packages(console):
    """Check status of all globally installed packages."""
    console.print("\n[bold blue]Checking Global Packages[/bold blue]")
    
    # Analysis progress messages with timing
    console.print("Analyzing global packages...")
    start_time = time.time()
    all_packages = get_all_packages(global_packages=True)
    analysis_time = time.time() - start_time
    console.print(f"Analysis completed in {analysis_time:.2f}s")
    
    console.print("Checking for updates...")
    start_time = time.time()
    outdated = get_outdated_packages(global_packages=True)
    update_check_time = time.time() - start_time
    console.print(f"Updates check completed in {update_check_time:.2f}s")
    
    if not all_packages:
        return
    
    outdated_map = {pkg['name']: pkg for pkg in outdated}
    
    # Display current state
    console.print("\n[bold]Global Package Status:[/bold]")
    display_version_table(console, all_packages, outdated_map)
    
    return all_packages, outdated

def list_backups():
    """List available backup files sorted by date (newest first)."""
    backup_dir = "package_backups"
    if not os.path.exists(backup_dir):
        return []
    
    backups = []
    try:
        for file in os.listdir(backup_dir):
            if file.startswith("package_versions_") and file.endswith(".json"):
                backups.append(os.path.join(backup_dir, file))
    except OSError as e:
        print(f"\nError listing backups: {e}")
        return []
    
    return sorted(backups, reverse=True)  # Most recent first

def main():
    """Main function with interactive menu and styled output."""
    try:
        console = Console()
        console.print("\n[bold blue]Package Version Manager[/bold blue]")
        
        # Initial choice between project and global packages
        questions = [
            inquirer.List('scope',
                         message='What would you like to check?',
                         choices=['Project Libraries', 'Global Libraries'])
        ]
        
        answers = inquirer.prompt(questions)
        
        if not answers:
            return

        if answers['scope'] == 'Project Libraries':
            requirements_files = find_requirements_files()
            if not requirements_files:
                console.print("\n[red]No requirements files found in the current directory![/red]")
                return
                
            req_question = [
                inquirer.List('requirements_file',
                             message='Select requirements file:',
                             choices=requirements_files)
            ]
            
            req_answer = inquirer.prompt(req_question)
            if not req_answer:
                return
                
            result = check_project_packages(console, req_answer['requirements_file'])
            if not result:
                return
            all_packages, outdated = result
            
        else:  # Global Libraries
            result = check_global_packages(console)
            if not result:
                return
            all_packages, outdated = result
        
        # Display total and outdated package counts with color
        console.print(f"\n[blue]Total package(s): {len(all_packages)}[/blue]")
        if outdated:
            console.print(f"[yellow]Found {len(outdated)} outdated package(s)[/yellow]")
        else:
            console.print("\n[green]All packages are up to date![/green]")
        
        # Action menu
        action_questions = [
            inquirer.List('action',
                         message='What would you like to do?',
                         choices=[
                             'Update all packages',
                             'Create backup only',
                             'Restore from backup',
                             'Exit'
                         ])
        ]

        action_answers = inquirer.prompt(action_questions)
        
        if not action_answers:
            return
            
        if action_answers['action'] == 'Update all packages':
            # Create backup before updating
            console.print("\n[bold]Creating backup...[/bold]")
            backup_file = create_backup(all_packages)
            if backup_file:
                console.print(f"[green]Created backup: {backup_file}[/green]")
                
                # Perform update
                console.print("\n[bold]Updating packages...[/bold]")
                update_packages(outdated, console, answers['scope'] == 'Global Libraries')
                console.print("\n[green]Package update process completed![/green]")
            
        elif action_answers['action'] == 'Create backup only':
            console.print("\n[bold]Creating backup...[/bold]")
            backup_file = create_backup(all_packages)
            if backup_file:
                console.print(f"[green]Created backup: {backup_file}[/green]")
            
        elif action_answers['action'] == 'Restore from backup':
            backups = list_backups()
            if not backups:
                console.print("\n[red]No backups found![/red]")
                return
                
            backup_questions = [
                inquirer.List('backup',
                             message='Select backup to restore:',
                             choices=backups)
            ]
            
            backup_choice = inquirer.prompt(backup_questions)
            if backup_choice:
                console.print("\n[bold]Restoring packages...[/bold]")
                if restore_packages(backup_choice['backup'], console):
                    console.print("\n[green]Package restoration completed![/green]")
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
