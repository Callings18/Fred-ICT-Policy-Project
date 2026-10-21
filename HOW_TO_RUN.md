# How to run this project on any computer

This guide is for Windows, macOS, and Linux. Follow the steps in order. You do not create the application database by hand. The first start creates a database named `ipmcs` and fills it with demonstration staff, devices, rules, and alerts.

## 1. Requirements

Install these before you clone the project.

| Requirement | What to install | Notes |
| --- | --- | --- |
| Python | Python 3.11 or newer | `python --version` or `python3 --version` should show 3.11 or higher. |
| Database | MySQL 8, or MariaDB 10.4 or newer | The application speaks the MySQL protocol. One server on port 3306 is enough. |
| Git | Git | Used only to download the project. |
| Browser | Any current browser | The site opens at http://127.0.0.1:5050 |

Python packages are listed in `requirements.txt` and installed in step 5. You do not install them one by one.

| Package | Purpose |
| --- | --- |
| Flask 3 | The web application |
| PyMySQL | The connection to MySQL or MariaDB |

Flask also installs its own supporting packages, including Werkzeug and Jinja2. You do not add those yourself.

The database account must be allowed to create a database. The `root` account can do that. If you use another account, that account needs the `CREATE` privilege.

A `.env` file is not read automatically. Settings are read from the environment. Step 6 shows how to set them. If you leave them unset, the application expects MySQL on this computer, port 3306, user `root`, and an empty password. That matches a default XAMPP install. A normal MySQL install usually has a root password, so set `IPMCS_DB_PASSWORD` in that case.

## 2. Install and start the database

Install one database server and start it. Leave it running while you use the application.

**Windows, XAMPP.** Install XAMPP, open the XAMPP Control Panel, and start MySQL. That service is MariaDB and works with this application. Do not install a second MySQL on port 3306.

**Windows, MySQL.** Install MySQL Server, then start the MySQL service from Services, or run:

```text
net start MySQL80
```

The service name can differ. Use the name shown in Services if `MySQL80` is not found.

**macOS, Homebrew.**

```text
brew install mysql
brew services start mysql
```

For MariaDB, use `brew install mariadb` and `brew services start mariadb`.

**Linux, Debian or Ubuntu.**

```text
sudo apt update
sudo apt install mysql-server
sudo systemctl enable --now mysql
```

For MariaDB, install `mariadb-server` and start `mariadb` instead.

Check that the server accepts a login. Replace the password if yours is not empty. An empty password is only the XAMPP default.

```text
mysql -u root -p -e "SELECT VERSION();"
```

If this command fails, fix the database login before you continue. The application cannot start without it.

## 3. Download the project

```text
git clone https://github.com/Callings18/Fred-ICT-Policy-Project.git
cd Fred-ICT-Policy-Project
```

## 4. Create a Python environment

From inside the project folder:

**Windows**

```text
python -m venv .venv
.venv\Scripts\activate
```

If `python` is not recognised, try `py -3` in place of `python`.

**macOS and Linux**

```text
python3 -m venv .venv
source .venv/bin/activate
```

The prompt shows `(.venv)` when the environment is active. Use this same terminal for the next steps.

## 5. Install the Python requirements

```text
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

On macOS and Linux, use `python3` if `python` is not available.

## 6. Set the database password and keys

Skip this step only when the database user is `root` and the password is empty.

Set the variables in the same terminal, before you start the application. Replace the sample values.

**Windows PowerShell**

```text
$env:IPMCS_DB_HOST = "127.0.0.1"
$env:IPMCS_DB_PORT = "3306"
$env:IPMCS_DB_USER = "root"
$env:IPMCS_DB_PASSWORD = "the-database-password"
$env:IPMCS_DB_NAME = "ipmcs"
$env:IPMCS_SECRET = "change-this-to-a-long-private-string"
$env:IPMCS_API_KEY = "change-this-to-another-private-string"
```

**Windows Command Prompt**

```text
set IPMCS_DB_HOST=127.0.0.1
set IPMCS_DB_PORT=3306
set IPMCS_DB_USER=root
set IPMCS_DB_PASSWORD=the-database-password
set IPMCS_DB_NAME=ipmcs
set IPMCS_SECRET=change-this-to-a-long-private-string
set IPMCS_API_KEY=change-this-to-another-private-string
```

**macOS and Linux**

```text
export IPMCS_DB_HOST=127.0.0.1
export IPMCS_DB_PORT=3306
export IPMCS_DB_USER=root
export IPMCS_DB_PASSWORD=the-database-password
export IPMCS_DB_NAME=ipmcs
export IPMCS_SECRET=change-this-to-a-long-private-string
export IPMCS_API_KEY=change-this-to-another-private-string
```

| Variable | Meaning | Used when unset |
| --- | --- | --- |
| `IPMCS_DB_HOST` | Database computer | `127.0.0.1` |
| `IPMCS_DB_PORT` | Database port | `3306` |
| `IPMCS_DB_USER` | Database user | `root` |
| `IPMCS_DB_PASSWORD` | Database password | empty |
| `IPMCS_DB_NAME` | Database name | `ipmcs` |
| `IPMCS_SECRET` | Signs the browser session | a local development value |
| `IPMCS_API_KEY` | Key for the collector API | `ipmcs-demo-collector` |
| `PORT` | Web address port | `5050` |

These values last only for that terminal window. Set them again each time you open a new terminal. `.env.example` lists the same names. Copying it to `.env` does not apply them, because the application does not load that file.

## 7. Start the application

```text
python run.py
```

Wait until the terminal prints:

```text
Running on http://127.0.0.1:5050
```

Leave this terminal open. Closing it, or pressing Ctrl+C, stops the site.

The first start creates `ipmcs` and loads the demonstration records. The next start keeps whatever is already in that database.

## 8. Open the site and sign in

Open http://127.0.0.1:5050

Every demonstration account uses the password `Monitor#2026`.

| Username | Name | Role |
| --- | --- | --- |
| `admin` | Fred Likasi | System Administrator |
| `officer` | Bupe Zulu | ICT/Security Officer |
| `manager` | Patrick Sakala | Management |
| `hr` | Thandiwe Lungu | HR Officer |

Change that password, `IPMCS_SECRET`, and `IPMCS_API_KEY` before anyone other than you uses the application.

## 9. Stop, then start it again later

1. In the terminal running `python run.py`, press Ctrl+C.
2. Stop the database only when you are finished with it. You can leave it running.

Next time:

1. Start the database service.
2. Open a terminal in the project folder.
3. Activate `.venv` with the command from step 4.
4. Set the variables from step 6 if your database has a password.
5. Run `python run.py`.
6. Open http://127.0.0.1:5050

You do not install the requirements again unless `requirements.txt` changes.

## 10. Optional check

With the database running and the environment active:

```text
python -m unittest discover -s tests -v
```

The tests use a separate database named `ipmcs_test` and delete it when they finish. They do not change `ipmcs`. The same database user must be allowed to create and drop that database.

## If it does not start

**`Can't connect to MySQL server`.** The database service is stopped, or the host and port are wrong. Start MySQL or MariaDB and repeat the login check in step 2.

**`Access denied for user`.** The user or password does not match the server. Set `IPMCS_DB_USER` and `IPMCS_DB_PASSWORD` to a working account, in the same terminal, then run `python run.py` again.

**`Access denied` while creating the database.** The account can log in but cannot create a database. Use `root`, or grant that account the `CREATE` privilege.

**`python` is not recognised.** On Windows, install Python from python.org and tick “Add python.exe to PATH”, then open a new terminal. You can also call `py -3` instead of `python`. On macOS and Linux, use `python3`.

**Port 5050 is already in use.** Something else is using that port. In the same terminal, set `PORT` to another number, for example `5051`, and open http://127.0.0.1:5051

**The page opens but sign-in fails.** Use the usernames in the table and the password `Monitor#2026`. Those accounts exist after the first successful start.
