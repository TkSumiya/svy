# $Id$

package mysession;
use Digest::MD5 qw(md5_hex);
use Fcntl qw(:DEFAULT);
use strict;
my $SESSION_DIR = "session/";

# セッションを作成
# セッションID を返す
#   セッションファイルが開けない場合は空文字列を返す
# $expire には有効期限を分単位で指定
sub mysession_new {
    my ( $ses, $expire ) = @_;
    my $REMOTE_ADDR = $ENV{'REMOTE_ADDR'} || "";
    my ( $sid, $c, $md5hash, $date );

    do {
	$c = _random_hex(8);
	$md5hash = md5_hex ("riise\n$REMOTE_ADDR\n$c\n" . time() . "\n$$");
	$sid = $md5hash . $c;
	main::logging(_session_file($sid));
    } while ( -e ( _session_file($sid) ) );

    $date = _date_string();
    $$ses{cdate} = $date;
    $$ses{ctime} = time();
    $$ses{host}= $REMOTE_ADDR;
    if ( $expire == 0 ) {
	$$ses{expire} = 0;
    } else {
	$$ses{expire} = time()+$expire*60;
    }

    if ( mysession_write_var ( $sid, %$ses ) < 0 ) {
	$sid = "";
    }
    
    debug_str ( $md5hash );
    debug_str ( $c );

    return $sid;
}


# セッションファイルを開き、変数を書き込む
# 改行コードは "\EOL" に置換
# ファイルが書き込み用に開けない場合 -1 を返す
sub mysession_write_var {
    my ( $sid, %ses )  = @_;
    my ( $sfile, $key, $val );

    return -1 if ( !_valid_sid($sid) );
    $sfile = _session_file($sid);

    debug_str ( "sfile = $sfile" );

    if ( ! sysopen ( FD, $sfile, O_WRONLY|O_CREAT|O_TRUNC, 0600 ) ) {
	return -1;
    }

    foreach $key ( sort keys %ses ) {
	$val = $ses{$key};
	$val =~ s/\n/\\EOL/g;
	print FD "$key:$val\n";
    }
    close ( FD );

    return 0;
}

sub debug_str {
    my ( $str ) = @_;
    return 0;
    print "<p><font color=\"gray\">$str</font></p>\n";
}

# セッションを廃棄
# セッションファイルを削除する
sub mysession_destroy {
    my ( $sid ) = @_;
    return if ( !_valid_sid($sid) );
    unlink ( _session_file($sid) );
}


# セッションを開く
# 正しくない場合、1 を返す。
# タイムアウトの場合 2 を返す。
# OK の場合、ファイルに保存されている変数を $ses にセットして帰る
sub mysession_open {
    my ( $sid, $ses ) = @_;
    my ( $sfile, $ret );

    return ( 1 ) if ( !_valid_sid($sid) );

    # session ファイルが存在するかどうかをチェック
    $sfile = _session_file($sid);
    ( -r  $sfile  ) || return ( 1 );

    $ret = mysession_read_var ( $sid, $ses );

    if ( $$ses{'expire'}>0 && $$ses{'expire'} < time() ) {
	return ( 2 );
    }
    
    return ( 0 );
}  

# セッションを閉じる
# $expire に >0 がセットされていたら、有効期限を更新 (分単位で指定)
sub mysession_close {
    my ( $sid , $ses, $expire ) = @_;
    my ( $date );

    return -1 if ( !_valid_sid($sid) );

    if ( $expire>0 ) {
	$$ses{'expire'} = time()+$expire*60;
    }
    
    $date = _date_string();
    $$ses{'adate'} = $date;
    $$ses{'atime'} = time();
    return mysession_write_var ( $sid, %$ses );
}

# セッションファイルを開き、変数を読み込む
sub mysession_read_var {
    my ( $sid, $ses ) = @_;
    my ( $sfile, $line, $key, $val );

    return 0 if ( !_valid_sid($sid) );
    $sfile = _session_file($sid);
    
    (-r $sfile) || return 0;
    
    open ( FD, "<", $sfile ) || return 0;
    while ( $line = <FD> ) {
	chomp ( $line );
	if ( $line =~ /^([^:]+):(.*)$/ ) {
	    $key = $1;
	    $val = $2;

	    $val =~ s/\\EOL/\n/g;
	    $$ses{$key} = $val;
	}
    }
    close ( FD );
    return 1;
}

sub _valid_sid {
    my ($sid) = @_;
    return defined($sid) && $sid =~ /^[0-9a-f]{48}$/;
}

sub _session_file {
    my ($sid) = @_;
    return $SESSION_DIR . $sid;
}

sub _date_string {
    my @d = localtime();
    return sprintf("%04d/%02d/%02d %02d:%02d:%02d",
		   $d[5]+1900, $d[4]+1, $d[3], $d[2], $d[1], $d[0]);
}

sub _random_hex {
    my ($bytes) = @_;
    my $buf = "";
    if ( open( URANDOM, "<", "/dev/urandom" ) ) {
	binmode URANDOM;
	read(URANDOM, $buf, $bytes);
	close(URANDOM);
    }
    while ( length($buf) < $bytes ) {
	$buf .= pack("LLL", time(), $$, int(rand(0xffffffff)));
    }
    return unpack("H*", substr($buf, 0, $bytes));
}

1;
