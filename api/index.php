<?php
    header("Access-Control-Allow-Origin: *");
    header("Content-type: application/json;charset=utf-8");

    function com2string($str) {
        $str = htmlspecialchars($str);
        $str = str_replace(array("\n", '\n', "\r", '\r'), array('<br>', '<br>'), $str);
        return $str;
    }

    include("../../../../dashboard.inc");
    $db = pg_connect("host=$dashboard_server dbname=$dashboard_db user=$dashboard_user password=$dashboard_pass");

    $request_array = explode('/', $_SERVER['REQUEST_URI']);
    $set = end($request_array);
    while ($set != 'api')
        $set = prev($request_array);
    $set = prev($request_array);

    $response = array();
    $query = 'SELECT distinct(dataset) FROM transfer WHERE set=\'' . $set . '\'and date(now() - interval \'10 days\') < tstamp AND tstamp < date(now())';
    $out = pg_query($query);
    $datasets = array();;
    while ($row = pg_fetch_row($out)) {
        array_push($datasets, $row[0]);
    }
    $response['datasets'] = $datasets;

    foreach ($datasets as $dataset) {
        $test_data = array();
        $query = 'SELECT source FROM transfer WHERE date(now() - interval \'10 days\') < tstamp AND tstamp < date(now()) UNION SELECT destination FROM transfer WHERE set=\'' . $set . '\' and date(now() - interval \'10 days\') < tstamp AND tstamp < date(now())';
        $out = pg_query($query);
        $endpoints = array();;
        while ($row = pg_fetch_row($out)) {
            array_push($endpoints, $row[0]);
        }
        $test_data['endpoints'] = $endpoints;

        $query = 'SELECT date(min(tstamp)), date(max(tstamp)) FROM transfer WHERE set=\'' . $set . '\' and dataset=\'' . $dataset . '\' AND date(now() - interval \'10 days\') < tstamp AND tstamp < date(now())';
        $out = pg_query($query);
        $row = pg_fetch_row($out);
        $test_data['start'] = $row[0];
        $test_data['end'] = $row[1];

        $query = 'SELECT source, destination, date(tstamp), status, rate, faults, message FROM transfer WHERE set=\'' . $set . '\' and dataset=\'' . $dataset . '\' AND date(now() - interval \'10 day\') < tstamp AND tstamp<date(now()) ORDER BY source, destination, tstamp';
        $out = pg_query($query);
        $transfers = array();
        while ($row = pg_fetch_assoc($out)) {
            extract($row);
            $transfer = array(
                'source' => $source,
                'destination' => $destination,
                'tstamp' => $date,
                'status' => (int) $status,
                'rate' => (int) $rate,
                'faults' => (int) $faults,
                'message' => com2string($message)
            );
            array_push($transfers, $transfer);
        }
        $test_data['transfers'] = $transfers;
        $response[$dataset] = $test_data;
    }

    http_response_code(200);
    echo json_encode($response);
?>
