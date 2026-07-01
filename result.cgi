#! /usr/bin/perl
# usage: result.cgi [-is n | -stat] qfile

#use lib './pms';
use strict "vars";
#require 'cgi-lib.pl';
use Jcode;

my $debug=0;
my $show_remote_user=0;
####################################################################
# グローバル変数定義
####################################################################
my $default_css = "survey.css";
my $default_home_url="./";

my $script = "result.cgi";

# qfile: 質問を記述したファイル (引数から読み込む)
my ($qfile);

my $nkf="/usr/bin/nkf";
# resultdir: アンケート結果が保存されているディレクトリ ($resultdir/$qfile.dat に入っているはず)
# is: 動作モード (引数から読み込む)
# csvcode: csv ファイルの文字コード (引数から読み込む mac|win|unix)
# $text: 表示すべき回答者番号 (引数から読み込む)
my ($resultdir,$is,$csvcode,$text);

# $firstq: 最初の問題番号 (qfile から読み込む)
# $lastq: 最後の問題番号 (qfile から読み込む)
my ($firstq,$lastq);
my (%qattr); # title, firstq, lastq, password

# password_from_cookie: クッキーから読み込んだパスワード (crypt されている)
# password_from_form: フォーム入力されたパスワード (平文)
# cookie_to_send: 新しく認証が行なわれた際に送るクッキー (HTTP ヘッダの一行となる形)
my ($password_from_cookie,$password_from_form,$cookie_to_send);

# @password $qfile から読みこんだパスワード
# @rq 表示結果を制限するための質問番号
# @ra 表示結果を制限するための質問に対する回答
# PASSSWD: hogehoge → hogehoge が入力されたら全ての結果を表示
# PASSSWD: hogehoge 1 2 → hogehoge が入力されたら質問1の値が2の結果だけを表示

my (@password,@rq,@ra,$rq,$ra);
$rq=$ra=-1;

# @fq to store question
#  $i is for question number
# $fq[$i][0] -> question type (S=single choice, M=multiple choice, T=Text)
#                              SN, MN to horizontal layout
# $fq[$i][1] -> dummy (for collect answer)
# $fq[$i][2] -> question sentence
# $fq[$i][3] -> possible choice for answer (array)

# @fa に回答を保存
#  $i は回答者の番号
#  $j は質問の番号
#  $fa[$i][0]: 配列 (日付, 時間, dummy, ホスト名, ホストIP, フォワードホスト名, フォワードホストIP, ユーザ名)
#  $fa[$i][$j]: 回答 (複数選択問題に対しては配列、その他はスカラ)

my (@fq,@fa,@fc,@fe,@fextra);

@fq=();
@fa=();
@fc=();
@fe=();
@fextra=();

my ( @to_eval );

$resultdir = "./result";

$is = -1; # -1 for index, 0 for stat, -2 for list answer, -3 for csv download
          # 1-n for each answer
$text = -1;

####################################################################
# 引数をパース
####################################################################

if ( $ARGV[0] eq "-down" ) {
    $is=-3;
    shift;
    $csvcode=$ARGV[0];
    ( $csvcode =~ /^(?:windows|unicode|mac|unix)$/ ) || fatal ( "Invalid csv code" );
    shift;
} elsif ( $ARGV[0] eq "-is" ) {
    shift;
    $is = $ARGV[0];
    ( $is =~ /^[0-9-][0-9]*$/ ) || fatal ( "Invalid page" );
    shift;
} elsif ( $ARGV[0] eq "-t" ) {
    shift;
    $text = $ARGV[0];
    ( $text =~ /^[0-9]+$/ ) || fatal ( "Invalid text number" );
    shift;
} elsif ( $ARGV[0] eq "-stat" ) {
    $is = 0;
    shift;
}

if ( $qfile eq "" ) {
    $qfile=$ARGV[0];
    shift;
}

####################################################################
# 本処理
####################################################################

# 認証の為のパスワード読み込み

$password_from_cookie = read_password_from_cookie();
$password_from_form = read_password_from_forminput();

# 質問ファイル名の妥当性チェック

( $qfile =~ /^[a-zA-Z0-9._-]+$/ ) || fatal ( "Invalid file ($qfile)" );

$qfile || fatal("Question file is not specified.\n");
(-f "$qfile.def" ) || fatal("Question file is not exist.\n");

# 質問・回答ファイルから読み込む (@fa, @fq が満たされる)

read_question($qfile);
$firstq = $qattr{firstq};
$lastq = $qattr{lastq};
# 認証
# 必要無ければスルー、必要であればサブルーチン内でフォーム入力のためのHTMLを
# 吐き出して終了

check_auth();

read_answer();

# 全回答結果のCSVダウンロード

if ( $is == -3 ) {
    csv_download();
    exit(0);
}

print_header();

debug_str(sprintf("n.of.fa=%d",$#fa));

if ( $is == -1 ) {
    # 表紙を表示
    show_index();
} elsif ( $is == -2 ) {
    # 個別回答の一覧表示
    list_answers();
} elsif ( $is == 0 ) {
    # 集計結果表示
    show_stat();
} else  {
    # $text 番目の個別回答を表示
    show_answer($is);
}

print_trailer();

exit(0);

####################################################################
# 本処理ここまで
####################################################################

####################################################################
# テキスト形式の設問に対する全回答を表示
sub show_text {
    my ($i)=@_;
    my ($j, $nna, $na);

    printf ( "<a href=\"javascript:toggle_disp('%s')\" class=\"toggle_text\">自由記述の回答を表示/非表示</a>\n", "text".$i );

    printf ( "<div id='%s' style='display:none'>\n", "text".$i );
    for ( $j=0; $j<=$#fa; ++$j ) {
	next if filter($i,$j);
	if ( $fa[$j][$i] eq "" ) {
	    ++$nna;
	    next;
	} else {
	    printf ( "<p class=\"t\"><a href=\"$script?-is+%d+%s\" target=\"_blank\">%s</a></p>\n", 
		     $j+1, $qfile,
		     escape_tag($fa[$j][$i]) );
	    ++$na;

	}
    }

#    printf ( "<a href=\"javascript:toggle_disp('%s')\" class=\"toggle_text\">回答を表示/非表示</a>\n", "text".$i );
    print ( "</div>\n" );

    printf ( "<p>(回答 %d 件、未回答 %d 件)</p>\n", $na, $nna );
}

####################################################################
# HTML タグを除去
sub escape_tag {
    my $str = shift;
    $str =~ s/&/&amp;/g;
    $str =~ s/</&lt;/g;
    $str =~ s/>/&gt;/g;
    $str =~ s/\\EOL/<br>/g;
    return $str;
}

sub escape_attr {
    my $str = escape_tag(shift);
    $str =~ s/"/&quot;/g;
    return $str;
}

####################################################################
# 設問ファイル読み込み
#sub read_question {
#    my ($q,$type,$correct,$question);
#    my @candidate;
#    open ( Q, "$qfile" );
#
#    $q=0;
#    $firstq=1;
#    while ( <Q> ) {
#	next if /^#/;
#	next if ( /^$/ );
#	chomp;
#	if ( /^NEXT:(.*)$/ ) {
#	    next;
#	} elsif ( /^FIRSTN:(.*)$/ ) {
#	    $firstq = $q = $1-1;
#	}elsif ( /^PASSWORD:[ ]*(.*)$/ ) {
#	    $password = $1;
#	}elsif ( /^PASSWD:[ ]*(.*)$/ ) {
#	    $password = $1;
#	} elsif ( /^TITLE:(.*)$/ ) {
#	    next;
#	}elsif ( /^Q/ ) {
#	    ++$q;
#	    #($type,$correct,$question) = (split( ':', $_ ))[1..3]
#	    @{$fq[$q]} = (split( ':', $_ ))[1..3];
#	    @candidate=();
#	    while ( <Q> ) {
#		next if /^#/;
#		chomp;
#		if ( /^$/ ) {
#		    last;
#		}
#		if ( /^A:(.*)$/ ) {
#		    push (@candidate,$1);
#		}
#	    }
#	    $fq[$q][3]=[@candidate];
#	}
#    }
#    $lastq = $q;
#    close(Q);
#}

####################################################################
# 回答ファイル読み込み
#sub read_answer {
#    my ( $i, @tmp, $d1, $d2 );
#    open ( R, "$resultdir/$qfile.log" );
#
#    while ( <R> ) {
#	next if ( /^#/ );
#	if ( /^$/ ) {
#	    ++$i;
#	    next;
#	}
#	chomp;
#	if ( /^([0-9].*)$/ ) {
#	    @tmp = split ( " ", $1 );
#	    $fa[$i][0] = [@tmp];
#	} elsif ( /^Q([0-9][0-9]): (.*)$/ ) {
#	    $d1=$1; $d2=$2;
#	    if ( $fq[$d1][0] =~ /^M/ ) {
#		@tmp = split ( "\0", $d2 );
#		$fa[$i][$d1] = [@tmp];
#	    } else {
#		$fa[$i][$d1] = $d2;
#	    }
#	} 
#    }
#    close(R);
#}

####################################################################
#sub calc_cum {
#    my ($n,@res)=@_;
#    my ($i,@cum,$sum);
##    $n = $#res+1;
#    for ( $i=0; $i<6; ++$i ) {
#	$cum[$i]=();
#    }
#    for ( $i=0; $i<$n; ++$i ) {
#	$sum += $res[$i];
#    }
#    print "SUM=$sum\n";
#    for ( $i=0; $i<$n; ++$i ) {
#	$cum[0][$i] = $res[$i];
#	$cum[1][$i] = sprintf("%5.1lf%%",$cum[0][$i]/$sum*100);
##	$cum[2][$i] = $res[$i]+$cum[2][$i-1];
##	$cum[3][$i] = sprintf("%5.1lf%%",$cum[2][$i]/$sum*100);
##	$cum[4][$n-1-$i] += $res[$i]+$cum[4][$n-1-$i+1];
##	$cum[5][$n-1-$i] = sprintf("%5.1lf%%",$cum[4][$n-1-$i]/$sum*100);
#    }
#    @cum;
#}
#

sub filter {
    my ($i,$j)=@_;
    my $nextloop;
    my $to_eval;

    if ( $#to_eval>=0 ) {
	$nextloop=0;
	foreach my $to_eval ( @to_eval ) {
#	    logging("in filter() to_eval=".$to_eval);
	    if (! eval($to_eval)) {
		return 1;
	    }
	}
    }
    return 0;
}
####################################################################
# 集計結果を表示
sub show_stat {
    my ( $ie,$i,$j,$k,@a, @res, @cum, $N );
    my $color_back="c0.gif";
    my $color_single="c2.gif";
    my $color_multi="c3.gif";
    my $clen = 100;
    my $chei = 12;
    
    printf("<a href=\"$script?$qfile\">[戻る]</a>\n");

#    for ( $i=$firstq; $i<=$lastq; ++$i ) {
    for ( $ie=0; $ie<=$#fe; ++$ie ) {
	if ( $fe[$ie][0] eq "Q" ) {
	    $i=$fe[$ie][1];
	} else {
	    if ( $fe[$ie][0] eq "IF" ) {
		print ( "<div class=\"group\">\n" );
		printf ( "<p class=\"groupdesc\">%s</p>\n", $fe[$ie][1] );
		push(@to_eval,$fe[$ie][2]);   # ごめん to_eval はグローバル変数だ
#		logging("to_eval=".join("/",@to_eval));
	    } elsif ( $fe[$ie][0] eq "FI" ) {
		print ( "</div>\n" );
		pop(@to_eval);
	    }
	    next;
	}

	printf ( "<p class=\"q\">質問%d: %s</p>\n", $i, $fq[$i][2] );
	printf ( "<blockquote>\n" );
	if ( $fq[$i][0] =~ /^T/ ) {
#	    printf ( "<a href=\"$script?-t+$i+$qfile\">回答を閲覧する</a><br>" );
	    show_text($i);
	} elsif ( $fq[$i][0] =~ /^S/ ) {
	    @res=();
	    $N=0;
	    for ( $j=0; $j<=$#fa; ++$j ) {
		next if filter($i,$j);
		if ( $fa[$j][$i] < 0 ) { # 未回答
		    ++$res[0];
		} else {
		    ++$res[$fa[$j][$i]+1];
		}
		++$N;
	    }
	    if ( $N ) {
		print "<table>\n";
		print "<thead><tr><td>回答数</td><td>割合</td><td>選択肢 (単一回答)</td><td>&nbsp;</td></tr></thead><tbody>\n";
#	    for ( $j=1; $j<=$#{$fq[$i][3]}+1; ++$j ) {
		foreach $j ( (1..$#{$fq[$i][3]}+1,0) ) {
		    my ($answer,$extratext)=("","");
		    if ( $j>0 ) {
			($answer,$extratext)=summary_extra_text($fq[$i][3][$j-1]);
		    }
		    printf ( "<tr style=\"border: 1px\"><td align=right>%d</td><td align=right>%5.1lf%%</td><td>%s%s</td><td><nobr><img src=\"$color_single\" height=%d width=%d><img src=\"$color_back\" height=%d width=%d></nobr></td></tr>\n", 
			     $res[$j],$res[$j]/$N*100,
			     ($j==0)? "<span class=\"mikaitou\">未回答</span>":$answer,
			     $extratext,
			     $chei, int($res[$j]/$N*$clen),
			     $chei, $clen-int($res[$j]/$N*$clen)
			     );
#			     ($j==0)? "<span class=\"mikaitou\">未回答</span>":$fq[$i][3][$j-1] );
		}
		print "</tbody></table>\n";
	    }  else {
		print "<p>回答なし</p>\n";
	    }
	} elsif ( $fq[$i][0] =~ /^M/ ) {
	    @res=();
	    $N=0;
	    for ( $j=0; $j<=$#fa; ++$j ) {
		next if filter($i,$j);
		for ( $k=0; $k<=$#{$fq[$i][3]}; ++$k ) {
		    $res[$k] += ${$fa[$j][$i]}[$k];
		}
	        ++$N;
	    }

	    if ( $N ) {
	       print "<table cellspacing=1>\n";
	       print "<thead><tr><td>回答数</td><td>割合</td><td>選択肢 (複数回答可)</td><td>&nbsp;</td></tr></thead><tbody>\n";
	       for ( $j=0; $j<=$#{$fq[$i][3]}; ++$j ) {
		    my ($answer,$extratext)=("","");
		    ($answer,$extratext)=summary_extra_text($fq[$i][3][$j]);
		   printf ( "<tr><td align=\"right\">%d</td><td>%5.1lf%%</td><td>%s%s</td><td><nobr><img src=\"$color_multi\" height=%d width=%d><img src=\"$color_back\" height=%d width=%d></nobr></td></tr>\n", 
			    $res[$j],$res[$j]/$N*100,$answer,$extratext,
			    $chei, int($res[$j]/$N*$clen),
			    $chei, $clen-int($res[$j]/$N*$clen)
			    );
#			    $res[$j],$res[$j]/$N*100,$fq[$i][3][$j] );
	       }
	       print "</tbody></table>\n";
	   } else {
	       print "<p>回答なし</p>\n";
	    }
	}
	printf ( "</blockquote>\n" );
    }
}
####################################################################
# 個別回答を表示
sub show_answer {
    my ( $is ) = @_; # 1 for first answer
    my ( $i,$j,@a );

    if ( $is>$#fa+1 ) {
	print "Invalid answer number\n";
	return;
    }

    printf("<a href=\"$script?-is+-2+$qfile\">[戻る]</a>\n");
    printf ( "[<a href=\"$script?%s\">←</a> ", 
	     ($is==1)? "-is+-2+$qfile":sprintf("-is+%d+$qfile", $is -1 ) );
    printf ( "(%d of %d)", $is, $#fa+1 );
    printf ( "<a href=\"$script?%s\">→</a>]\n", 
	     ($is==$#fa+1)? "-s+-2+$qfile":sprintf("-is+%d+$qfile", $is+1 ) );

    --$is;
#    for ( $i=$firstq; $i<=$lastq; ++$i ) {
    for ( my $ie=0; $ie<=$#fe; ++$ie ) {
	if ( $fe[$ie][0] eq "Q" ) {
	    $i=$fe[$ie][1];
	} else {
	    if ( $fe[$ie][0] eq "IF" ) {
		print ( "<div class=\"group\">\n" );
		printf ( "<p class=\"groupdesc\">%s</p>\n", $fe[$ie][1] );
	    } elsif ( $fe[$ie][0] eq "FI" ) {
		print ( "</div>\n" );
	    }
	    next;
	}
	printf ( "<p class=\"q\">質問%d: %s\n", $i, $fq[$i][2] );
	printf ( "<blockquote>\n" );
	if ( $fq[$i][0] =~ /^T/ ) {
	    printf ( "%s<br>", escape_tag($fa[$is][$i]) );
	} elsif ( $fq[$i][0] =~ /^S/ ) {
	    for ( $j=0; $j<=$#{$fq[$i][3]}; ++$j ) {
		if ( $fa[$is][$i] ne "" and $fa[$is][$i] == $j ) {
		    printf ( "● " );
		} else {
		    printf ( "○ " );
		}
		my ($c,$html)=check_extra_text($is,$fq[$i][3][$j]);
#		printf ( "%s<br>\n", $fq[$i][3][$j] );
		printf ( "%s%s<br>\n", $c,$html );
	    }
	} elsif ( $fq[$i][0] =~ /^M/ ) {
	    for ( $j=0; $j<=$#{$fq[$i][3]}; ++$j ) {
		if ( ${$fa[$is][$i]}[$j] == 1 ) {
		    printf ( "■ " );
		} else {
		    printf ( "□ " );
		}
		my ($c,$html)=check_extra_text($is,$fq[$i][3][$j]);
#		printf ( "%s<br>\n", $fq[$i][3][$j] );
		printf ( "%s%s<br>\n", $c,$html );
	    }
	}
	printf ( "</blockquote>\n" );
    }
    ++$is;

    printf("<a href=\"$script?-is+-2+$qfile\">[戻る]</a>\n");
    printf ( "[<a href=\"$script?%s\">←</a> ", 
	     ($is==1)? "-is+-2+$qfile":sprintf("-is+%d+$qfile", $is -1 ) );
    printf ( "(%d of %d)", $is, $#fa+1 );
    printf ( "<a href=\"$script?%s\">→</a>]\n", 
	     ($is==$#fa+1)? "-s+-2+$qfile":sprintf("-is+%d+$qfile", $is+1 ) );


}
####################################################################
# 表紙を表示
sub show_index {
    my @list;
    my ($nanswers);
    $nanswers = $#fa + 1;
    my $str = <<HTML;
<p>現在 $nanswers 件の回答があります。</p>

<ul>
 <li><a href="$script?-is+-2+$qfile">個別の回答を閲覧する</a></li>
 <li><a href="$script?-stat+$qfile">集計結果を閲覧する</a></li>
</ul>
HTML
    ;

    Jcode::convert(\$str,'utf-8');
    print $str;
}

####################################################################
# 回答の一覧(ヘッダのみ)テーブルで表示
sub list_answers{
    my @list;
    my ($nanswers, $i, $td);
    my ($remotehost, $forwardedhost, $remoteuser);
    $nanswers = $#fa + 1;

    printf("<a href=\"$script?$qfile\">[戻る]</a>\n");
    printf("[CSV形式でダウンロード <a href=\"$script?-down+unicode+$qfile\">unicode</a>, <a href=\"$script?-down+mac+$qfile\">mac</a>, <a href=\"$script?-down+windows+$qfile\">win</a>, <a href=\"$script?-down+unix+$qfile\">unix</a>]\n");
#    print ( "<div align=\"center\">\n" );
    $td = "td class=\"border_tb\"";
    print ( "<table cellspacing=0><thead><tr><$td>&nbsp;</td><$td>Date</td><$td>Time</td><$td>Remote Host</td><$td>Forwarded Host</td><$td>Remote User</td></tr></thead><tbody>\n" );
    for ( $i=0; $i<$nanswers; ++$i ) {
	$remotehost 
	    = ($fa[$i][0][3] eq "Unknown")? $fa[$i][0][4]:$fa[$i][0][3];

	if ( $fa[$i][0][5] eq "nil" ) {
	    $forwardedhost = "---";
	} else {
	    $forwardedhost 
		= ($fa[$i][0][5] eq "Unknown")? $fa[$i][0][6]:$fa[$i][0][5];
	}

	$remoteuser
	    = ($fa[$i][0][7] eq "nil")? "---":$fa[$i][0][7];

	$td = ( $i == $nanswers-1 )?  "td class=\"border_b\"":"td";
	printf ( "<tr><$td align=\"right\"><a href=%s>%d</a></td><$td>%s</td><$td>%s</td><$td>%s</td><$td>%s</td><$td>%s</td></tr>\n",
		 sprintf("\"$script?-is+%d+$qfile\"",$i+1),
		 $i+1, 
		 $fa[$i][0][0], 
		 $fa[$i][0][1],
		 $remotehost,
		 $forwardedhost,
		 $remoteuser );
    }
    print ( "</tbody></table>\n" );
#    print ( "</div>\n" );
}


####################################################################
sub fatal {
    my ($message)=@_;
    print "Content-type: text/plain\n\n";
    print "Fatal Error\n";
    print $message;
    exit(0);
}

####################################################################
sub print_question {
    my ($n,$str)=@_;
my $html =  <<"EOF"
<p class='q'>質問 $n: $str</p>
EOF
;

    Jcode::convert(\$html,'utf-8');
    print $html;
}

####################################################################
my $already_printed=0;
sub print_header {
    return if ( $already_printed );
    $already_printed=1;

    print ( "Content-type: text/html; charset=utf-8\n$cookie_to_send\n" );

    my $html = <<EOF;

<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8">
<meta http-equiv="Content-Style-Type" content="text/css">
<meta http-equiv="Content-Script-Type" content="text/javascript">
<title>Survey System</title>
<link rel=stylesheet type="text/css" href="survey.css">
<script type="text/javascript">
<!-- 
function toggle_disp(itemId) {
        var elem, disp;

        if (document.all) {
                elem = document.all(itemId);
        } else if (document.getElementById) {
                elem = document.getElementById(itemId);
        } 
        disp = elem.style.display;
        if(disp == "block") {
                disp = "none";
        } else {
                disp = "block";
        }
        elem.style.display = disp;
}
//-->
</script>
</head>
<body bgcolor="white">
<h1>「$qattr{title} ($qfile)」アンケート結果</h1>
EOF
;

    Jcode::convert(\$html,'utf-8');
    print $html;
}
####################################################################
sub print_title {
    my ($title)=@_;
    print <<"EOF";
<h1>$title</h1>
EOF
;
}
####################################################################
sub print_trailer {
    print <<EOF;
</body>
</html>
EOF
;
}

####################################################################
sub csv_download {
    my ($file_to_output,$i,$q,$c);
    my @lines;

    $file_to_output="$resultdir/tmp-$$.csv";

    if ( $csvcode eq "windows" ) {
	open ( CSV, "| $nkf -Lw -s >$file_to_output" );
    } elsif( $csvcode eq "unicode" ) {
	open ( CSV, "| $nkf -w8  >$file_to_output" );
    }else {
	open ( CSV, "| $nkf --$csvcode >$file_to_output" );
    }

    # CSV先頭行書き出し
    print CSV ( "Date,User,Host" );

    for ( $q=$firstq; $q<=$lastq; ++$q ) {
	if ( $fq[$q][0] =~ /^M/ ) {
	    for ( $c=0; $c<=$#{$fq[$q][3]}; ++$c ) {
		printf CSV ( ",Q%d-%d", $q, $c+1 );
	    }
	} else {
	    printf CSV ( ",Q%d", $q );
	}
    }

    for ( $i=0; $i<=$#fextra; ++$i ) {
	printf CSV ( ",XT for Q%s" , $fextra[$i] );
    }
    
    print CSV ( "\n" );

    # CSVデータ行書き出し
    for ( $i=0; $i<=$#fa; ++$i ) {
	printf CSV ( "%s %s,%s,\"%s\"",
		    $fa[$i][0][0], $fa[$i][0][1],
		    $fa[$i][0][7], $fa[$i][0][3]);
	for ( $q=$firstq; $q<=$lastq; ++$q ) {
	    if ( $fq[$q][0] =~ /^M/ ) {
		for ( $c=0; $c<=$#{$fq[$q][3]}; ++$c ) {
		    if ( ${$fa[$i][$q]}[$c] ) {
			 print CSV ( ",1" );
		     } else {
			 print CSV ( "," );
		     }
		}
	    } elsif ( $fq[$q][0] =~ /^S/ ) {
		if ( defined($fa[$i][$q]) and $fa[$i][$q]>=0 ) {
		    printf CSV ( ",%d", $fa[$i][$q] );
		} else {
		    printf CSV ( "," );
		}
	    } else {
		my $str = $fa[$i][$q];
		$str =~ s/\\EOL/\n/g;
		$str =~ s/"/""/g;
		printf CSV ( ",\"%s\"", $str );
	    }
	}
        for ( $q=0; $q<=$#fextra; ++$q ) {
           my $str = ${$fa[$i][$qattr{lastq}+1]}[$q];
	   $str =~ s/"/""/g;
	   printf CSV ( ",\"%s\"" , $str );
        }
	print CSV ( "\n" );
    }

    close ( CSV );



    printf ( "Content-type: %s\n"
	     . "Content-Disposition: attachment; filename=\"%s\"\n"
	     . "Content-Length: %d\n\n",
	     "application/octet-stream",
	     "$qfile.csv",
	     (stat($file_to_output))[7]  );

    if ( open ( OUT, "<", $file_to_output ) ) {
	while ( my $line = <OUT> ) {
	    print $line;
	}
	close ( OUT );
	unlink ( $file_to_output );
    }
}

####################################################################
# for auth
#

# URL encode
sub url_encode {
    my ( $value ) = @_;
    $value =~ s/([^\w\=\& ])/'%' . unpack("H2", $1)/eg;
    $value =~ tr/ /+/;
    return ( $value );
}

# URL decode
sub url_decode {
    my ($value)=@_;
    $value =~ s/\+/ /g;
    $value =~ s/%([0-9a-fA-F][0-9a-fA-F])/pack("C",hex($1))/eg;
    return $value;
}

# クッキーから p=hogehoge の hogehoge 部分を返す
sub read_password_from_cookie {
    my ($pair,$varname,$value);
    if ( $ENV{"HTTP_COOKIE"} ne "" ) {
	foreach $pair ( split ( "; ", $ENV{"HTTP_COOKIE"} ) ) {
	    ($varname,$value) = split ( "=", $pair );
	    if ( $varname eq "p" ) {
		return url_decode($value);
	    }
	}
    }
    return "";
}

# フォーム入力からパスワードを読み込んで返す
sub read_password_from_forminput {
    my ($pair,$input,$varname,$value, $password);
    $password="";
    $input = <>;
    foreach $pair ( split ( "&", $input ) ) {
	($varname,$value) = split ( "=", $pair );
	if ( $varname eq "p" ) {
	    $password = url_decode($value);
	} elsif ( $varname eq "qfile" ) {
	    $qfile = url_decode($value);
	}
    }
    return $password;
}

# IPアドレスをつけてパスワードをクリプトする
sub crypt_password {
    my ($passwd) = @_;
    $passwd .= $ENV{'REMOTE_ADDR'};
    return crypt ( $passwd, "Cy" );
}

# (クッキーとして送られて来た)パスワードが正しいかどうかをチェック
sub match_password {
    my ( $crypted, $plain )=@_;
    return ( crypt_password ( $plain) eq $crypted );
}

# パスワード入力のためのフォーム表示
sub show_password_form {
    print_header();

    my $html = <<"EOF";
<p>結果を表示するにはパスワードが必要です。</p>

    <form action="$script" method="post">
<input type="password" name="p">
<input type="hidden" name="qfile" value="$qfile">
<input type="submit" value="送信">
</form>
EOF
    ;

    Jcode::convert(\$html,'utf-8');
    print $html;
}    

# 質問ファイルで設定されたパスワードは $qattr{password} に入っている
sub check_auth {
    my $i;
    # $password なし
    return if ( $#password < 0 );

#    logging ( `date` );
#    logging ( "password=[".join(":",@password)."]" );
#    logging ( "password_from_cookie=[$password_from_cookie]" );
#    logging ( "password_from_form=[$password_from_form]" );

    # フォームから取得したものと設定パスワードが一致するか？
    if ( $password_from_form ) {
	for ( $i=0; $i<=$#password; ++$i ) {
	    if ( $password_from_form eq  $password[$i] ) {
		$cookie_to_send = sprintf ( "Set-Cookie: p=%s\n", 
					    url_encode(crypt_password($password_from_form)) );
		$rq=$rq[$i];
		$ra=$ra[$i];
		return;
	    }
	}
    }

    # クッキーから取得したものと設定パスワードが一致するか？
    if ( $password_from_cookie ) {
	for ( $i=0; $i<=$#password; ++$i ) {
	    if ( match_password ( $password_from_cookie, $password[$i] ) ) {
		$rq=$rq[$i];
		$ra=$ra[$i];
		return;
	    }
	}
    }
    
    # 一致しないもしくはクッキーがない
    show_password_form ();
    
    exit(0);
}

sub logging {
    my ($msg)=@_;
    open ( LOG,">>/tmp/cgi-log" );
    print LOG ( "$msg\n" );
    close(LOG);
}
####################################################################
# 設問ファイル読み込み
#
# 前堤としているグローバル変数
#    (@fq,@fc,@fa,@fe);
#    (%qattr); # title, firstq, lastq, password
#
# @fq to store question
#  $i is for question number
# $fq[$i][0] -> question type (S=single choice, M=multiple choice, T=Text)
#                              SN, MN to horizontal layout
# $fq[$i][1] -> dummy (for collect answer)
# $fq[$i][2] -> question sentence
# $fq[$i][3] -> possible choice for answer (array)
#
# @fc に条件を保存
#  $i 番の問題についてそれを表示するかいなかを
#  if ( eval ( $fc[$i] ) ) { ... }
#  で判断できる。
#
# @fe 「イベント」を保存。リストのリストを保持。
#  設問ファイルの順番に従い、$i 番目のイベントは
#  $fe[$i][0] : イベントの種類 Q:質問 NOTE:注意書き IF:条件開始 FI:条件終わり
#  $fe[$i][1] : イベントのパラメータ
#
# @fa に回答を保存
#  $i は回答者の番号
#  $j は質問の番号
#  $fa[$i][0]: 配列 (日付, 時間, dummy, ホスト名, ホストIP, フォワードホスト名, フォワードホストIP, ユーザ名)
#  $fa[$i][$j]: 回答 (複数選択問題に対しては配列、その他はスカラ)

sub read_question {
    my $qfile = shift;
    my ($q,$type,$correct,$question);
    my @candidate;
    my %lab;
    my @condition;
    my $e;
    open ( Q, "-|", $nkf, "-w", "-Lu", "$qfile.def" ) || fatal("Question file is not exist.\n");

    $q=$e=0;
    $qattr{firstq}=1;
    $qattr{style} = $default_css;
    $qattr{home_url} = $default_home_url;
    while ( <Q> ) {
	next if /^#/;
	next if ( /^$/ );
	chomp;
	if ( /^Q/ ) {
	    ++$q;
	    $fe[$e++] = [("Q",$q)];
	    $fc[$q]=($#condition>=0)? join(" and ", @condition):"1";
	    #($type,$correct,$question) = (split( ':', $_ ))[1..3]
	    @{$fq[$q]} = (split( ':', $_ ))[1..3];
	    @candidate=();
	    while ( <Q> ) {
		next if /^#/;
		chomp;
		if ( /^$/ ) {
		    last;
		}
		if ( /^A([+]*):(.*)$/ ) {
		    if ($1) {
			push (@fextra,sprintf("%d-%d",$q, $#candidate+1));
			push (@candidate,$2."_EXTRATEXT_".$#fextra);
		    } else {
			push (@candidate,$2);
		    }
		} elsif ( /^L:(.*)$/ or /^LABEL:(.*)$/ ) {
		    $lab{$1}=$q;
		} elsif ( /^FI:/ ) {
		    pop @condition;
		    $fe[$e++]=[("FI","")];
		}
	    }
	    $fq[$q][3]=[@candidate];
	}elsif ( /^NEXT:(.*)$/ ) {
	    next;
	}elsif ( /^SHOW_REMOTE_USER:(.*)$/ ) {
	    chomp $1;
	    if ($1 eq "yes") {
		$show_remote_user=1;
	    }
	}elsif ( /^FIRSTN:(.*)$/ ) {
	    $qattr{firstq} = $q = $1-1;
	}elsif ( /^PASSWORD:[ ]*(.*)$/ or /^PASSWD:[ ]*(.*)$/ ) {
	    my $l = $1;
	    if ( $l =~ /^(\S+)\s+(\d+)\s+(\d+)$/ ) {
		push ( @password, $1 );
		push ( @rq, $2 );
		push ( @ra, $3 );
	    } else {
		push ( @password, $l);
		push ( @rq, -1 );
		push ( @ra, -1 );
	    }
	}elsif ( /^TITLE:(.*)$/ ) {
	    $qattr{title} = $1;
	    next;
	}elsif ( /^STYLE:(.*)$/ ) {
	    $qattr{style} = $1;
	    $qattr{style} =~ s/ //g;
	    if ( -e ($qattr{style} . ".css") ) {
		$qattr{style} .= ".css";
	    } elsif ( ! -e $qattr{style} ) {
		$qattr{style} = $default_css;
	    }
	    next;
	}elsif ( /^HOME:(.*)$/ ) {
	    $qattr{home_url} = $1;
	    $qattr{home_url} =~ s/ //g;
	    next;
	}elsif ( /^NOTE:(.*)$/ ) {
	    $fe[$e++] = [("NOTE",$1)];
	    next;
	}elsif ( /^NEWPAGE:/ ) {
	    $fe[$e++] = [("NEWPAGE","")];
	    next;
	}elsif ( /^IF:(.*)$/ ) {
	    my $condstr=$1;
	    my $condtitle=$1;

	    foreach my $k ( keys %lab ) {
		$condstr =~ s/(\$$k)\[/\${\$fa[\$j][$lab{$k}]}\[/g;
		$condstr =~ s/(\$$k)/\$fa[\$j][$lab{$k}]/g;
		$condtitle =~ s/(\$$k)/質問$lab{$k}($k)/g;
	    }

#	    logging("condstr=$condstr");
	    push ( @condition, $condstr );
	    $fe[$e++] = [("IF",
			  $condtitle,
			  $condition[$#condition]
			  )];
#	    my $condstr=$1;
#	    $condstr =~ /[\s]*([\w]+)[\s]*([=!<>]+)[\s]*([\d]+)[\s]*$/;
#	    if ( defined ( $lab{$1} ) ) {
#		push ( @condition, sprintf("\$fa[%d]%s%s",$lab{$1},$2,$3) );
#		$fe[$e++] = [("IF",sprintf("Q%d %s %s", $lab{$1}, $2, $fq[$lab{$1}][3][$3]))];
#	    } else {
#		push ( @condition, "1");
#	    }
	}elsif ( /^FI:/ ) {
	    pop @condition;
	    $fe[$e++]=[("FI","")];
	}
    }
    $qattr{lastq} = $q;
    close(Q);
}


# @fa に回答を保存
#  $j は質問の番号
#  $fa[0]: 配列 (日付, 時間, dummy, ホスト名, ホストIP, フォワードホスト名, フォワードホストIP, ユーザ名)
#  $fa[$j]: 回答 (複数選択問題に対しては配列、その他はスカラ)

sub read_answer {
    my @f;
    my $n;
    my $i;
    open ( R, "$resultdir/$qfile.log" );

    $n=0;
    while(<R>){
	chomp;
	@f = split ( "\0",$_ );

	my $c=0;
	$fa[$n][0]=[(split(" ",$f[0]),"",$f[2],$f[3],"nil","nil",$f[6])];

	if ( ! $show_remote_user ) {
	    $fa[$n][0][7]="nil";
	}


	$c=8;
	for ( $i=1; $i<=$qattr{lastq}; ++$i ) {
	    if ( $fq[$i][0] =~ /^T/ ) {
		if ( $f[$c] eq "-1" ) {
		    $fa[$n][$i] = "";
		} else {
		    $fa[$n][$i] = $f[$c];
		}
		++$c;
	    }elsif ( $fq[$i][0] =~ /^M/ ) {
		my @tmp;
		for ( my $j=0; $j<=$#{$fq[$i][3]}; ++$j ) {
#		    logging( "($i,$j)=$f[$c]\n" );
		    push ( @tmp, $f[$c++] );
	        }
#		logging ( sprintf("Q%d, n of candidate: %d\n", $i, $#{$fq[$i][3]} ) );
		$fa[$n][$i]=[@tmp];
#		logging ( join(":",@{$fa[$n][$i]} ) );
#		    ${$fa[$n][$i]}[$j] = $f[$c++];
	    }else {
		$fa[$n][$i] = $f[$c];
		++$c;
	    }
        }

	$fa[$n][$i]=[()];
	for ( my $j=0; $j<=$#fextra;++$j ) {
	    push(@{$fa[$n][$i]},$f[$c++]);
	}

	if ( $rq>=0 and $ra>=0 ) {
	    if ( $fa[$n][$rq]!=$ra ) {
		pop (@fa);
		next;
	    } else {
		debug_str("\$rq=$rq \$ra=$ra \$i=$i  " . $fa[$n][$rq]);
	    }

	}
        ++$n;
    }

    close(R);
}

sub debug_str {
    my $str=shift;
    return if ($debug==0);
    print_header();
    printf("<p style=\"color: #00c\">%s</p>\n",escape_tag($str));
}

sub check_extra_text {
    my ($n,$str) = @_;
    my $c=$str;
    my $html="";
    if ( $str =~ /^(.*)_EXTRATEXT_(\d+)$/ ) {
	$c = $1;
	my $et_input = ${$fa[$n][$qattr{lastq}+1]}[$2];
#	&jcode'convert(\$et_input,'sjis');
	$html = sprintf("&nbsp;&nbsp;(%s)"
		       ,( $et_input ne "")? escape_tag($et_input):"&nbsp;&nbsp;"
		       );
    }
    return($c,$html);
}

sub summary_extra_text {
    my ($str) = @_;
    my $c=$str;
    my $html="";
    my $nanswers = $#fa + 1;
    my $n_et;
    my @et_list=();
    my $id;
    if ( $str =~ /^(.*)_EXTRATEXT_(\d+)$/ ) {
	$id = "xt".$2;
	$c = sprintf ( "<a href=\"javascript:toggle_disp('%s')\" class=\"toggle_text\">$1</a>\n", $id );
	$n_et = $2;
	debug_str("c= $c, n_et= $n_et");
	for ( my $i=0; $i<$nanswers; ++$i ) {
	    my $et_input = ${$fa[$i][$qattr{lastq}+1]}[$n_et];
	    push(@et_list,$et_input) if ( $et_input ne "" );
        }
        $html = sprintf("<div id='%s' style='display:none'><p class=\"t\">%s</p></div>\n",$id,escape_tag(join(", ",uniq_c(@et_list))) );
    }
    return($c,$html);
}


sub uniq_c {
    my @a=sort(@_);
    my @b=();
    my $p="";
    my $n=0;

    foreach my $c ( @a ) {
	if($p eq $c){
	    ++$n;
	} else {
	    push ( @b, "$p ($n)" ) if ( $p ne "" );
	    $n=1;
	    $p=$c;
	}
    }
    push ( @b, "$p ($n)" );
    return @b;
}
