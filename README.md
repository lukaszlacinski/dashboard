# Globus Dashboard
The dashboard dynamically creates and updates a web page with effective transfer rates of Globus transfers run in both directions between a set of Globus endpoints. The dashboard includes three components:
- cron script with configuration files (in cron/) that runs test transfers daily
- REST API (in api/) that provides transfer results for the last 10 days
- dashboard HTML page (in app/) that displays transfer results obtained from the REST API

### Create the database
Switch user to postgres and:
```
postgres=# create database dashboard;
postgres=# create user dashboard with encrypted password '<password>';
postgres=# grant all privileges on database dashboard to dashboard;
```
Switch to your user account and check if you can connect to the database:
```
$ psql -h localhost -U dashboard dashboard
Password for user dashboard:
dashboard=>
```

### Prepare test data sets
Go to each endpoint and create directories with test data sets. For example
```
$ mkdir 20_5_GB
$ cd 20_5_GB
$ for ((i=1;i<=20;i=i+1)); then head -c 5G </dev/urandom >$i.5G; done
```

### Describe sets of endpoints and datasets
Create a json file that lists:
- endpoints between you want to run data transfers
- "name" - name of the endpoint that will be displayed on the dashboard
- "uuid" - UUID of the Globus endpoint
- "src_path" - a directory with data sets (the dashboard transfers test datasets from <src_path>/<dataset_name>)
- "dst_path" - a directory where all data sets will be transferred to
- data sets you want to transfer between the endpoints. Name of the dataset must be the same as a name of the directory with the data set. Name of the dataset is also displayed on the dashboard page after replacing underscore characters '_' with a space.

Sample configuration files: [cron/endpoints_aps.json](cron/endpoints_aps.json), [cron/endpoints_ecp.json](cron/endpoints_ecp.json).

### Register with Globus
Go to https://developers.globus.org to register the cron script as a Globus app. When registering, select 'Native App' toggle button.

### Set up a cron job
Create local_settings.py file with credentials to the database and Globus:
```
database = {
    "url": "postgresql://dashboard:<password>@localhost:5432/dashboard"
}
globus = {
    "client_id": "<client_id>",
    "redirect_uri": "https://auth.globus.org/v2/web/auth-code",
    "scopes": "openid urn:globus:auth:scope:transfer.api.globus.org:all"
}
```
Create Python virtual environment and install prerequisite modules
```
$ python3 -mvenv venv
$ . venv/bin/active
(venv) $ pip install -r cron/requirements.txt
```
Modify cron/dashboard.sh script as needed and add the cron job
```
$ crontab -e
0 0 * * * <path>/dashboard.sh
```

### Set up the REST API
Install Apache and PHP packages
```
# yum install httpd php php-pgsql
```
Copy [api/index.php](api/index.php) to HTTPD server directory, `<DocumentRoot>/<endpoints_set_name>/api/`. Copy [api/dashboard.inc](api/dashboard.inc) with database credentials to a directory, so the file is included by [api/index.php#L11](api/index.php#L11).

### Set up the dashboard web page 
Copy [app/index.html](app/index.html) and [app/wz_tooltip.js](app/wz_tooltip.js) to HTTPD server directory `<DocumentRoot>/<endpoints_set_name>/`.
