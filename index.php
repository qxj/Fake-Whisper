<?php
// index.php --- Time-stamp: <Julian Qian 2011-08-30 00:17:46>
// Copyright 2011 Julian Qian
// Author: junist@gmail.com
// Version: $Id: index.php,v 0.0 2011/08/28 16:12:40 jqian Exp $
// Keywords:

define('WHISPER_PATH', '/var/tmp/whisper/');

if(($db = sqlite_open("/var/tmp/whisper.db")) === FALSE){
    die();
}

if(empty($_GET["id"])){
    /* fetch documents recent 1 month */
    $sql = "select * from files where downloaded=0 and timestamp>UNIX_TIMESTAMP()-2592000 limit 30";
    $query = sqlite_query($db, $sql);
    while($entry = sqlite_fetch_array($query, SQLITE_ASSOC)){
        echo sprintf("http://%s%s?id=%s", $_SERVER["HTTP_HOST"],
                $_SERVER["REQUEST_URI"], $entry["fileid"]);
    }

}else{
    $fileid = $_GET["id"];
    $sql = "select * from files where fileid='$fileid' limit 1";
    $query = sqlite_query($db, $sql);
    if($entry = sqlite_fetch_array($query, SQLITE_ASSOC)){
        if($entry["filetype"] == "pdf"){
            header("Content-Type: application/pdf");
        }else if($entry["filetype"] == "mobi"){
            header("Content-Type: application/x-mobipocket-ebook");
        }else{
            die();
        }
        header("Content-Disposition: attachment; filename=".$entry["filename"]);
        header("Content-Length: ".$entry["filesize"]);
        $filepath = whipser_path($entry["fileid"].".".$entry["filetype"]);
        readfile($filepath);

        /* mark the downloaded file */
        $sql = "update files set downloaded=1 where fileid='$fileid'";
        sqlite_query($db, $sql);
    }
}

function whisper_path($filename){
    return WHISPER_PATH.$fielname;
}

?>