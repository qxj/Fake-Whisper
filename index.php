<?php
// index.php --- Time-stamp: <Julian Qian 2011-10-29 20:18:27>
// Copyright 2011 Julian Qian
// Author: junist@gmail.com
// Version: $Id: index.php,v 0.0 2011/08/28 16:12:40 jqian Exp $
// Keywords:

define('WHISPER_PATH', '/var/tmp/whisper/');

/* orz...sqlite_open() only works for sqlite2 @@ */
$db = new PDO("sqlite:/var/tmp/whisper.db");

if(empty($_GET["id"])){
    /* fetch documents recent 1 month */
    $sql = "select * from files where downloaded=0 and timestamp>strftime('%s', 'now')-2592000 limit 30;";
    foreach($db->query($sql) as $entry){
        echo sprintf("http://%s%s?id=%s\n", $_SERVER["HTTP_HOST"],
                $_SERVER["REQUEST_URI"], $entry["fileid"]);
    }
}else{
    $fileid = $_GET["id"];
    $sql = "select * from files where fileid='$fileid' limit 1;";
    foreach($db->query($sql) as $entry){
        if($entry["filetype"] == ".pdf"){
            header("Content-Type: application/pdf");
        }else if($entry["filetype"] == ".mobi"){
            header("Content-Type: application/x-mobipocket-ebook");
        }else{
            header("HTTP/1.0 404 Not Found");
            die();
        }
        header("Content-Disposition: attachment; filename=\"".urlencode($entry["filename"]).$entry["filetype"]."\"");
        header("Content-Length: ".$entry["filesize"]);
        $filepath = whisper_path($entry["fileid"].$entry["filetype"]);
        readfile($filepath);
		/* mark the downloaded file */
		$sql = "update files set downloaded=1 where fileid='".$entry["fileid"]."';";
		$db->query($sql);
		break;
    }
}

function whisper_path($filename){
    return WHISPER_PATH.$filename;
}

?>
