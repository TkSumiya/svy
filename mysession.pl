# $Id$

package mysession;
use Digest::MD5 qw(md5_hex);
use strict;
my $SESSION_DIR = "session/";

# セッション作成
# セッションID を返す
#   セッションファイルが作れない場合空文字列を返す
# $expire には有効期限を分単位で設定
sub mysession_new {
    my ( $ses, $expire ) = @_;
    my $REMOTE_ADDR = $ENV{'REMOTE_ADDR'};
    my ($sid,$c,$md5hash,$sfile,$date);

    # 乱数初期化
    srand(time ^ ($$ + ($$ << 15)));

    # セッションID生成
    # (字列"riise") + (remote host アドレス) + (0-1000 の乱数の16進表示)
    # を md5 ハッシュ値を計算、ハッシュ値の末尾に上の乱数を加えたものを
    # セッションIDとして割り当てる
    do {
	$c=sprintf("%x",rand(1000));
	$md5hash = md5_hex ("riise\n$REMOTE_ADDR\n$c");
	$sid = $md5hash . $c;
	$sfile = $SESSION_DIR . $sid;
	main::logging($sfile);
    } while ( -e ( $sfile ) );


    $date = `date '+%Y/%m/%d %H:%M:%S'`;
    chomp ( $date );
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
    $sfile = $SESSION_DIR . $sid;

    debug_str ( "sfile = $sfile" );

#    (-w $sfile) || return (-1);

    if ( ! open ( FD, ">$sfile") ) {
	return -1;
    }

#    while (list ($key, $val) = each ($ses) ) {
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
    unlink ( $SESSION_DIR . $sid );
}


# セッションを開く
# 正しくない場合、1 を返す。
# タイムアウトの場合 2 を返す。
# OK の場合、ファイルに保存されている変数を $ses にセットして帰る
sub mysession_open {
    my ( $sid, $ses ) = @_;
    my $REMOTE_ADDR=$ENV{'REMOTE_ADDR'};
    my ( $md5hash, $c, $sfile, $ret );

    # session id が正しいかどうかをチェック
#    $md5hash = substr($sid,0,32);
#    $c = substr($sid,32);
#    if ( $md5hash != md5_hex ( "riise\n$REMOTE_ADDR\n$c" ) ) {
#	return ( 1 );
#    }

    # session ファイルが存在するかどうかをチェック
    $sfile = $SESSION_DIR . $sid;
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

    if ( $expire>0 ) {
	$$ses{'expire'} = time()+$expire*60;
    }
    
    $date = `date '+%Y/%m/%d %H:%M:%S'`;
    chomp ( $date );
    $$ses{'adate'} = $date;
    $$ses{'atime'} = time();
    return mysession_write_var ( $sid, %$ses );
}

# セッションファイルを開き、変数を読み込む
sub mysession_read_var {
    my ( $sid, $ses ) = @_;
    my ( $sfile, $line, $key, $val );

    $sfile = $SESSION_DIR . $sid;
    
    (-r $sfile) || return 0;
    
    open ( FD, $sfile );
    while ( $line = <FD> ) {
      chomp ( $line );
      if ( $line =~ /^([^:]+):(.*)$/ ) {
	  $key = $1;
	  $val = $2;

#	  print "$key, $val\n";
	  $val =~ s/\\EOL/\n/g;
	  $$ses{$key} = $val;
      }
  }
    close ( FD );
    return 1;
}
