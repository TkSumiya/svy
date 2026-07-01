#! /usr/bin/perl

#use lib './pms';
#use lib './pms/i386-linux-thread-multi';
use strict "vars";
require './cgi-lib.pl';
require './mysession.pl';
#require './auth.pl';
use Jcode;
use Time::HiRes;

####################################################################
# グローバル変数定義
####################################################################
my $debug=0;
my $script="q.cgi";

my $default_home_url="./";
my $error_url="error.php";
my $default_css = "survey.css";

# 2007/10/27
# 「その他 (     ) 」に対応したい。
# 問題ファイルの対応する選択肢を A+:... とコーディング。
# 問題ファイル読み込み時に、問題文末尾に "+EXTRATEXT" と追加
# 同時に @fextra に "X-Y" と言う文字列を保存していく。
#   X問目のY番目の選択肢に追加テキストあり、と言う意味
# 回答は、配列(@fa)の末尾にテキストのリストを追加する。
# HTML フォームのテキストエリアには "XTi" (i=0..$#fextra) という名前を与える

my (@fq,@fc,@fa,@fe,@fextra);
my %qattr;

my @sc; # 条件づけの判断の結果を入れる

my ( $q,$type,$correct,$question,@candidate,$nexturl,$title);
my ( %ses, $sid );

my $cids=0;

my $nkf = "/usr/bin/nkf";

my %inputv;

    if ( $qfile !~ /^[a-zA-Z0-9._-]+$/ ) {
	logging("Invalid question file name.");
	fatal("Invalid question file.\n");
    }

if ( $ses{qfile} !~ /^[a-zA-Z0-9._-]+$/ ) {
    logging("Invalid question file name in session.");
    fatal("Invalid question file.\n");
}

my $reqchecked=0; # 提出一歩手前までいって、必須項目チェックをした

####################################################################

ReadParse( \%inputv );

if ( ! $inputv{sid} ) {
    my ( $qfile );

    $qfile=$ARGV[0];

    shift;
    if ( ! $qfile ) {
	logging("Question file is not specified.");
	fatal("Question file is not specified.\n");
    }
    
    if (! -f "$qfile.def" ) {
	logging("Question file is not exist.");
	fatal("Question file is not exist.\n");
    }

    $sid = mysession::mysession_new( \%ses, 300 );

    logging("New session ($sid) created." );

    $ses{qfile} = $qfile;
    $ses{shown} = -1;
} else {
    my $retval;
    $sid = $inputv{sid};
    $retval = mysession::mysession_open( $sid, \%ses );
    if ( $retval != 0 ) {
	logging("Session error.($retval)");
	redirect_url($error_url);
	exit;
    }
    if ( $ses{saved} ) {
	logging("Double vote.");
	redirect_url($ses{home_url});
	exit;
    }
}

read_question ( $ses{qfile} );
$ses{home_url} = $qattr{home_url};

print_header("utf-8");
print_title ($qattr{title});

if ( $qattr{expire} ne "" ) {
    if ( $qattr{expire} =~ m|^(\d+)/(\d+)/(\d+) (\d+):(\d+)| ) {
	my $expired_date = sprintf("%4d%02d%02d.%02d%02d",$1,$2,$3,$4,$5);
	my @d = localtime();
	my $current_date = sprintf("%4d%02d%02d.%02d%02d",
				$d[5]+1900,$d[4]+1,$d[3],$d[2],$d[1]);
	if ( $current_date > $expired_date ) {
	    logging("Expired survey");
	    print_expired();
	    exit;
	}
    }
}


#logging("l=".$inputv{login_name});
#if ( $inputv{login_name} eq '73860318' ) {
#    logging("p=".$inputv{login_passwd});
#    logging("p=".ord($inputv{login_passwd}));
#}

if($qattr{auth} ne "" and $ses{auth_user} eq "") {
    my $msg="";
    if ( $inputv{login_name} and $inputv{login_passwd} ) {
	if(auth( $inputv{login_name}, $inputv{login_passwd} )) {
	    if ( $qattr{auth_pat} ne "" && ! ( $qattr{auth_pat} eq 'all' ) ) {
		if ( $inputv{login_name} =~ /$qattr{auth_pat}/ ) {
		    $ses{auth_user}=$inputv{login_name};
		    logging( "pattern check done. auth done for ". $inputv{login_name} );
		} else {
#		    $msg="<span class=\"error\">Authorization failed</span>: あなたはこのアンケートには答えられません。/You do not meet the requirement for this survey.<br>";
		    $msg="<span class=\"error\">Authorization failed</span>: あなたはこのアンケートには答えられません。/This survey is not for you.<br>";
		    logging( "invalid id pattern for ". $inputv{login_name} );
		}
	    } else {
		$ses{auth_user}=$inputv{login_name};
		logging( "auth done for ". $inputv{login_name} );
	    }
	} else {
	    $msg="<span class=\"error\">Authentification failed</span>: ユーザIDまたはパスワードが違います。/Incorrect user ID or password.<br>";
	    logging( "invalid id or password for ". $inputv{login_name} );
	}
    }

    if( $ses{auth_user} eq "") {
	show_login($msg);
	mysession::mysession_close($sid,\%ses,0);
	exit;
    }
}
    

read_answer();

$ses{shown} = $inputv{shown} if ( $inputv{shown} );

# 要回答問題の回答状況を調べる
logging(sprintf("%d ?=? %d",$ses{shown},$#fq ));
if ( $ses{shown}+1==$#fq and check_answers()==0 ) {
    $reqchecked=1;
    my $msg = "<p class=\"error\">必須項目で未回答のものがあります。</p>\n";
    $ses{shown}=-1;
    Jcode::convert(\$msg,'utf-8');
    print $msg;
}

if ( $inputv{final} ) {
    save_nsv();
    print_thankyou();
    $ses{saved}=1;
    logging(sprintf("saved for %s.", $sid ));
  mysession::mysession_close($sid,\%ses,0);
  mysession::mysession_destroy($sid,\%ses,0);
    exit;
}

logging(sprintf("shown=%d for %s.", $ses{shown}, $sid ));

my $haveshown=0;
my $boo;
@sc = (1);

for ( my $i=0; $i<=$#fe; ++$i ) {
    if ( $fe[$i][0] eq "IF" ) {
	if ( eval ($fe[$i][2]) ) {
	    push ( @sc, 1 );
	} else {
	    push ( @sc, 0 );
	}
    } elsif ( $fe[$i][0] eq "FI" ) {
	pop ( @sc );
    }

#printf "<p><font color=\"red\">$i / $#fe / $ses{shown}</font></p>\n";
#printf "<p><font color=\"red\">%s</font></p>\n", join(":",@sc);

    next if ( $i<=$ses{shown} );
    $ses{shown}=$i;

    last if ( $haveshown and $fe[$i][0] eq "IF" );

    $boo=1;
    foreach ( @sc ) {
	$boo = ($boo and $_);
    }
    next if ( not $boo );

    if ( $fe[$i][0] eq "Q" ) {
	$q = $fe[$i][1];
#	print ( "<p><font color=\"red\">$q $fc[$q]</font>\n" ) if $debug;
#	print ( "<p><font color=\"brown\">$fa[5] , $fa[16]</font>\n" ) if $debug;;
#	if ( $q>$ses{shown} && eval($fc[$q]) ) {
	    print_question ( $q  );
	    print_candidate ( $q );
#	    $ses{shown}=$q;
	    $haveshown=1;
#	}
#    } elsif ( $fe[$i][0] eq "NOTE" and $q>=$ses{shown} ) {
    } elsif ( $fe[$i][0] eq "NOTE" ) {
	print_note( $fe[$i][1] );
#	print ( "<p>$q:$ses{shown}</p>\n" );
    } elsif ( $haveshown and ($fe[$i][0] eq "IF" or $fe[$i][0] eq "NEWPAGE") ) {
	last if not $qattr{ignore_newpage};
    }
}

print_trailer($nexturl,$haveshown);
$ses{nsvanswer}=make_nsv_answer();
mysession::mysession_close($sid,\%ses,0);

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
    my ($n)=@_;
    my $str = $fq[$n][2];
    my $required = ($fq[$n][4])? "<span class=\"required\">要回答</span>":"";
    Jcode::convert(\$required,'utf-8');
    my $class = "q";

    if ( $reqchecked and $fq[$n][4]==1 and check_answer($n)==0 ) {
	$class .= " unanswered";
    }
    
print <<"EOF"
<p class="$class">Q $n: $str$required</p>
EOF
;
}
# ####################################################################
# sub print_candidate {
#     my ($n,$type,@str)=@_;
#     my ($c,$nstr,$typestr,$i,$br);
#     $nstr = sprintf ( "\"Q%02d\"", $n );
#     print "<blockquote>\n";
#     if ( $type eq "SM" ) {
# 	print "<select name=$nstr>\n";
# 	$i=0;
# 	foreach $c ( @candidate ) {
# 	    print "<option value=\"$i\"> $c\n";
# 	    ++$i;
# 	}
# 	print "</select>\n";
#     } elsif( ($type =~ /^S/) || ($type =~ /^M/) ) {
# 	$br = ( $type =~ /N$/ )? "":"<br>";
# 	$typestr = ( $type =~ /^S/ )? "\"radio\"":"\"checkbox\"";
# 	$i=0;
# 	foreach $c ( @candidate ) {
# 	    print "<input type=$typestr name=$nstr value=\"$i\">\n";
# 	    print "$c$br\n";
# 	    ++$i;
# 	}
#     } elsif ( $type eq "T" ) {
# 	print "<input name=$nstr size=50><br>\n";
#     } elsif ( $type eq "TM" ) {
# 	print "<textarea name=$nstr cols=80 rows=5></textarea><br>\n";
#     }
#     print "</blockquote>\n";
# }

sub check_extra_text {
    my ($str,$id) = @_;
    my $c=$str;
    my $html="";
    if ( $str =~ /^(.*)_EXTRATEXT_(\d+)$/ ) {
	$c = $1;
	my $et_input = ${$fa[$qattr{lastq}+1]}[$2];
	Jcode::convert(\$et_input,'utf-8');
	$html = sprintf("&nbsp;&nbsp;<input type=\"text\" size=%d name=\"%s\" value=\"%s\" onchange=\"AutoCheck('%s');\">"
		       ,( $et_input ne "-1")? escape_attr($et_input):""
		       ,"XT".$2  # 名前
		       ,( $et_input ne "-1")? $et_input:""
                       ,$id
#		       ,($fextra[$2] ne "-1")? $fextra[$2]."($2)":""
		       );
    }
    return($c,$html);
}

sub print_candidate {
    my ($n)=@_;
    my ($c,$nstr,$typestr,$i,$br);
    my $type = $fq[$n][0];
    my @candidate = @{$fq[$n][3]};
    my $extratext;

    $nstr = sprintf ( "\"Q%02d\"", $n );

    print "<blockquote>\n";
    if ( $type eq "SM" ) {
	print "<select name=$nstr>\n";
	$i=0;
	foreach $c ( @candidate ) {
	    my $checked = ($i==$fa[$n])? " selected":"";
	    print "<option value=\"$i\"$checked> $c$extratext\n";
	    ++$i;
	}
	print "</select>\n";
    } elsif( $type =~ /^S/ ) {
	$br = ( $type =~ /N$/ )? "":"<br>";
	$i=0;
	foreach $c ( @candidate ) {
	    my $checked = ($i==$fa[$n])? " checked":"";
	    my $idlabel="opt".$cids;
	    ++$cids;
	    ($c,$extratext)=check_extra_text($c,$idlabel);
	    print "<input type=\"radio\" id=\"$idlabel\" name=$nstr value=\"$i\"$checked>\n";
	    print "<label for=\"$idlabel\"><span class=\"labeltext\">$c</span></label>$extratext$br\n";
#	    print "<span class=\"labeltext\">$c</span>$extratext$br\n";
	    ++$i;
	}
    } elsif ( $type =~ /^M/ ) {
	$br = ( $type =~ /N$/ )? "":"<br>";
	$i=0;
	printf "<input type=\"hidden\" name=\"Q%02d-0\" value=1>\n", $n;
	foreach $c ( @candidate ) {
	    my $checked = ($fa[$n][$i])? " checked":"";
	    my $idlabel="opt".$cids;
	    ++$cids;
	    ($c,$extratext)=check_extra_text($c,$idlabel);
	    printf "<input type=\"checkbox\" id=\"$idlabel\" name=\"Q%02d-%d\" value=\"1\"$checked>\n", $n, $i+1;
	    print "<label for=\"$idlabel\">$c</label>$extratext$br\n";
	    ++$i;
	}
    } elsif ( $type eq "T" ) {
	my $str = ( $fa[$n] ne "-1")? " value=\"" . escape_attr($fa[$n]) . "\"":"";
	Jcode::convert(\$str,'utf-8');
	print "<input name=$nstr size=50$str><br>\n";
    } elsif ( $type eq "TM") {
	my $str = ( $fa[$n]  ne "-1")? escape_tag($fa[$n]):"";
	Jcode::convert(\$str,'utf-8');
	print "<textarea name=$nstr cols=80 rows=5>$str</textarea><br>\n";
    }
    print "</blockquote>\n";
}
####################################################################
sub print_header {
    my ( $charset ) = shift;
    print <<EOF;
Content-type: text/html; charset=$charset

<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=$charset">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Survey System</title>
<link rel=stylesheet type="text/css" href="$qattr{style}">
<script type="text/javascript"><!--
   function AutoCheck(checkname) {
      document.getElementById(checkname).checked = true;
   }
// --></script>
</head>
<body bgcolor="white">
<form action="$script" method="post" enctype="application/x-www-form-urlencoded">
EOF
;
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
sub print_note {
    my ($note)=@_;
    print <<"EOF";
<div class="note">
$note
</div>
EOF
;
}
####################################################################
sub print_trailer {
    my ($nexturl,$haveshown)=@_;
    my $lastmessage="";
    my $button="NEXT";

    if ( not $haveshown ) {
	$lastmessage = "
<div class=\"thankyou\"><p>回答を送信してもよいですか？</p></div>
<div class=\"thankyou\"><p>Are you sure to submit your answers?</p></div>
<p>修正がある場合は、ブラウザの「戻る」ボタンで戻って回答を入れ直してください。</p>
<p>If you want to change your answers, click the Back button on your browser.</p>
<input type=\"hidden\" name=\"final\" value=\"1\">";
	$button = "Submit";
	Jcode::convert(\$lastmessage,'utf-8');
	Jcode::convert(\$button,'utf-8');
    }


    print <<EOF;
$lastmessage
<input type="hidden" name="shown" value="$ses{shown}">
<input type="hidden" name="sid" value="$sid">
<p class="t2">
<!-- input type="submit" value="$button" -->
<button type="submit" value="$button" class="submit_button">$button</button>
</p>
</form>
</body>
</html>
EOF
;
}
####################################################################
sub print_thankyou {
    my $msg;
    $msg = "
<div class=\"thankyou\"><p>ありがとうございました。</p></div>
<p>回答は送信されました。</p>
<p>ご協力ありがとうございました。</p>

<div class=\"thankyou\"><p>Thank you!</p></div>
<p>Your answers were successfully submited.</p>
<p>Thank you for your cooperation.</p>

<hr>
<p><a href=\"$ses{home_url}\">Back</a></a>
</form>
</body>
</html>
";

    Jcode::convert(\$msg,'utf-8');

    print $msg;
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
# $fq[$i][4] -> required or not
#
    open ( Q, "-|", $nkf, "-w", "-Lu", "$qfile.def" ) || fatal("Question file is not exist.\n");
#  $i 番の問題についてそれを表示するかいなかを
#  if ( eval ( $fc[$i] ) ) { ... }
#  で判断できる。
#
# @fe 「イベント」を保存。リストのリストを保持。
#  設問ファイルの順番に従い、$i 番目のイベントは
#  $fe[$i][0] : イベントの種類 Q:質問 NOTE:注意書き IF:条件開始 FI:条件終わり
#  $fe[$i][1] : イベントのパラメータ
#  $fe[$i][2] : イベントのパラメータ2 (IF で eval に渡す論理式を入れる)
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
    open ( Q, "nkf -w -Lu $qfile.def |" );

    $q=$e=0;
    $qattr{firstq}=1;
    $qattr{condition}=0;
    $qattr{ignore_newpage}=0;
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
	    # 質問タイプが、"*"で終っていたら、必須の質問
	    if ( $fq[$q][0] =~ /^(.*)\*$/ ){
		$fq[$q][4] = 1;
		$fq[$q][0] = $1;
	    } else {
		$fq[$q][4] = 0;
	    }
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
	}elsif ( /^AUTH:(.*)$/ ) {
	    $qattr{auth} = $1;
	    logging ( sprintf ( "auth=%s", $qattr{auth} ) );
	    if ( $qattr{auth} =~ /^([\w]+) (.*)$/ ) {
		$qattr{auth} = $1;
		$qattr{auth_pat} = $2;
		logging ( sprintf ( "auth_pat=%s", $qattr{auth_pat} ) );
	    }
	}elsif ( /^FIRSTN:(.*)$/ ) {
	    $qattr{firstq} = $q = $1-1;
	}elsif ( /^PASSWORD:[ ]*(.*)[ ]*$/ ) {
	    $qattr{password} = $1;
	}elsif ( /^PASSWD:[ ]*(.*)[ ]*$/ ) {
	    $qattr{password} = $1;
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
	}elsif ( /^CONDITION:(.*)$/ ) {
	    $qattr{condition} = $1;
	    $qattr{condition} =~ s/ //g;
	    next;
	}elsif ( /^EXPIRE:(.*)$/ ) {
	    $qattr{expire} = $1;
	    $qattr{expire} =~ s/^[ ]*//g;
	    $qattr{expire} =~ s/[ ]*$//g;
	    next;
	}elsif ( /^IGNORENEWPAGE:(.*)$/ ) {
	    $qattr{ignore_newpage} = $1;
	    $qattr{ignore_newpage} =~ s/ //g;
	    next;
	}elsif ( /^NOTE:(.*)$/ ) {
	    $fe[$e++] = [("NOTE",$1)];
	    next;
	}elsif ( /^NEWPAGE:/ ) {
	    $fe[$e++] = [("NEWPAGE","")];
	    next;
	}elsif ( /^IF:(.*)$/ and $qattr{condition} ) {
	    my $condstr=$1;
	    my $condtitle=$1;

	    foreach my $k ( keys %lab ) {
		$condstr =~ s/(\$$k)\[/\${\$fa[$lab{$k}]}\[/g;
		$condstr =~ s/(\$$k)/\$fa[$lab{$k}]/g;
		$condtitle =~ s/(\$$k)/質問$lab{$k}($k)/g;
	    }

	    push ( @condition, $condstr );
	    $fe[$e++] = [("IF",
			  $condtitle,
			  $condition[$#condition]
			  )];
	}elsif ( /^FI:/ and $qattr{condition} ) {
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
#  $fa[n+1]: 追加テキストのリスト(nは質問の数)
#  $xt 番目の追加テキストは ${$fa[$qattr{lastq}+1]}[$xt] で参照できる

sub check_answers {
    logging("check requies");
    for ( my $i=1; $i<=$#fq; ++$i ) {
	if ( $fq[$i][4]==1 ) {
	    logging("question $i required");
	    return 0 if(check_answer($i)==0);
	}
    }
    return 1;
}

sub check_answer {
    my $i= shift;
    if ( $fq[$i][0] =~ /^M/ ){
	my $rck=0;
	foreach my $r ( @{$fa[$i]} ) {
	    $rck += $r;
	}
#	logging(sprintf("answer(%d)=[%d]",$i,$fa[$i])); 
	return 0 if ($rck==0);
    } elsif ( $fq[$i][0] =~ /^T/ ){
	return 0 if ( $fa[$i] eq "" );
    } else {
	return 0 if ( $fa[$i] == -1 )
    }

    return 1;
}

sub read_answer {
    my $key;

    retrieve_answer();

    foreach $key ( sort keys %inputv ) {
	if( $key =~ /^Q([\d]+)$/ ) {
	    my $q = $1;
	    if ( $fq[$q][0] =~ /^T/ ) {
		Jcode::convert(\$inputv{$key},'utf-8');
	    }
	    $fa[$q] = $inputv{$key};
	    print "<p><font color=\"blue\">$q = $inputv{$key};</font></p>\n" if $debug;
	} elsif ( $key =~ /^Q([\d]+)-([\d]+)$/ ) {
	    my $q = $1;
	    my $t = $2;
	    if ( $t==0 ) {
#		$fa[$q]=[()];
		for ( my $i=0; $i<=$#{$fq[$q][3]}; ++$i ) {
		    ${$fa[$q]}[$i]=0;
		}
	    } else {
		${$fa[$q]}[$t-1]=$inputv{$key};
	    }
	} elsif ( $key =~ /^XT([\d]+)$/ ) {
	    my $xt = $1;
            if ( defined($fextra[$xt]) ) {
		Jcode::convert(\$inputv{$key},'utf-8');
		${$fa[$qattr{lastq}+1]}[$xt]=$inputv{$key};
	    }
	}
    }
}

sub make_nsv_answer {
    my $csv = "";
    my $c;
    for ( my $i=1; $i<=$qattr{lastq}; ++$i ) {
	if ( $fq[$i][0] =~ /^M/ ) {
	    for ( my $j=0; $j<=$#{$fq[$i][3]}; ++$j ) {
		$csv .= (($csv ne "")? "\0":"") . ${$fa[$i]}[$j];
	    ++$c;
	    }
        } else {
     	    $csv .= (($csv ne "")? "\0":"") . $fa[$i];
	    ++$c;
        }
    }
    for ( my $i=0; $i<=$#fextra; ++$i ) {
     	    $csv .= (($csv ne "")? "\0":"") . ${$fa[$qattr{lastq}+1]}[$i];
    }
       
printf ("<p><font color=\"blue\">saved, c=%d</font></p>\n", $c) if $debug;
    return $csv;
}
		
sub make_csv_answer {
    my $csv = "";
    my $c;
    for ( my $i=1; $i<=$qattr{lastq}; ++$i ) {
	if ( $fq[$i][0] =~ /^M/ ) {
	    for ( my $j=0; $j<=$#{$fq[$i][3]}; ++$j ) {
		$csv .= (($csv ne "")? ",":"") . ${$fa[$i]}[$j];
	    ++$c;
	    }
        } elsif ( $fq[$i][0] =~ /^T/ ){
     	    $csv .= (($csv ne "")? ",":"") . "\"" . $fa[$i] . "\"";
	    ++$c;
        } else {
     	    $csv .= (($csv ne "")? ",":"") . $fa[$i];
	    ++$c;
        }
    }
printf ("<p><font color=\"blue\">saved, c=%d</font></p>\n", $c) if $debug;
    return $csv;
}
		
sub retrieve_answer {
    my @f;

#    print "retrieve_answer";
    if ( $ses{nsvanswer} ) {
	@f = split ( "\0",$ses{nsvanswer} );
	printf ("<p><font color=\"blue\">parsed, c=%d</font></p>\n", $#f) if $debug;
	printf ("<p><font color=\"blue\">a02, %s</font></p>\n", $f[1]) if $debug;
    } else {
	for ( my $i=1; $i<=$qattr{lastq}; ++$i ) {
	    if ( $fq[$i][0] =~ /^M/ ) {
		for ( my $j=0; $j<=$#{$fq[$i][3]}; ++$j ) {
		    push (@f,"0");
		}
	    }else {
		push ( @f, "-1" );
	    }
        }
	for ( my $i=0; $i<=$#fextra; ++$i ) {
	    push(@f,"-1");
	}
	printf ("<p><font color=\"blue\">created, c=%d, fextra=%d, f=[%s]</font></p>\n", $#f, $#fextra, join(":",@f) ) if $debug;
    }

    my $c=0;
    my $i;
    
    for ( $i=1; $i<=$qattr{lastq}; ++$i ) {
	if ( $fq[$i][0] =~ /^M/ ) {
	    $fa[$i]=[()];
	    for ( my $j=0; $j<=$#{$fq[$i][3]}; ++$j ) {
		${$fa[$i]}[$j] = $f[$c++];
	    }
        }else {
	    $fa[$i] = $f[$c++];
	}
    }
    $fa[$i]=[()];
    for ( my $j=0; $j<=$#fextra;++$j ) {
        push(@{$fa[$i]},$f[$c++]);
	printf ("<p><font color=\"blue\">push (i=%d)</font></p>\n", $i) if $debug;
    }
	printf ("<p><font color=\"blue\">pushed [%s] lastq=%d</font></p>\n"
		,join(":",@{$fa[$qattr{lastq}+1]})
		,$qattr{lastq}
		) if $debug;
}


sub parsecsv{
    my ($tmp) = @_;
    my @values;
    $tmp =~ s/(?:\x0D\x0A|[\x0D\x0A])?$/,/;
    @values = map {/^"(.*)"$/ ? scalar($_ = $1, s/""/"/g, $_) : $_}
                ($tmp =~ /("[^"]*(?:""[^"]*)*"|[^,]*),/g);
    @values;
}

####################################################################
sub escape_attr {
    my $str = escape_tag(shift);
    $str =~ s/"/&quot;/g;
    return $str;
}

# HTML タグを除去
sub escape_tag {
    my $str = shift;
    $str =~ s/&/&amp;/g;
    $str =~ s/</&lt;/g;
    $str =~ s/>/&gt;/g;
    return $str;
}

####################################################################
# NSVをファイルに書き出す
sub save_nsv {
    my @rh=getremotehost();
#    my $remoteuser=iceuser($rh[2]);
    my $remoteuser=$ses{auth_user};
    my $resultdir="result";
    my $logfile;
    my $lockfile;
    my ($sec,$min,$hour,$day,$mon,$year);
    my $date;
    my $i;

    $logfile=$ses{qfile};
    $logfile =~ s/\//_/g;
    $lockfile="/tmp/survey-".$logfile;
    $logfile="$resultdir/".$logfile.".log";


    ($sec,$min,$hour,$day,$mon,$year)=localtime;

    $date=sprintf("%4d/%02d/%02d %02d:%02d:%02d",
		  $year+1900, $mon+1, $day, $hour, $min, $sec );

    for ( $i=0; symlink($lockfile,$lockfile)==0; ++$i ) {
	Time::HiRes::sleep(0.1);
	unlink ( $lockfile ) if ( ($i+1)%30 == 0 );
    }

    open ( LOG, ">>$logfile" );
    printf LOG ("$date\0$i\0%s\0$remoteuser\0%s",
		join("\0",@rh), $ENV{'HTTP_USER_AGENT'});

    my $val = $ses{nsvanswer};
    $val =~ s/\n/\\EOL/g;

    print LOG "\0".$val;

    print LOG "\n";
    close ( LOG );
    unlink ( $lockfile );
}
    
####################################################################
sub getremotehost {
    my $remote_host=$ENV{'REMOTE_HOST'};
    my $remote_addr=$ENV{'REMOTE_ADDR'};
    my $forwarded_addr = $ENV{'HTTP_X_FORWARDED_FOR'};
    my $forwarded_host;

    if ( ! $remote_host ) {
	$remote_host
	    = gethostbyaddr ( pack ( 'C4', split(/\./,$remote_addr) ) , 2 );
	$remote_host="Unknown" if ( $remote_host eq '.' || $remote_host eq '' );
    }

    if ( $forwarded_addr ) {
	if ( $forwarded_addr =~ /^[0-9]/ ) {
        $forwarded_host =
            gethostbyaddr ( pack ( 'C4', split(/\./,$forwarded_addr) ), 2 );
    }
	$forwarded_host="Unknown" if ( $forwarded_host eq '' );
    }

    $forwarded_addr="nil" if ( $forwarded_addr eq '' );
    $forwarded_host="nil" if ( $forwarded_host eq '' );

    ($remote_host,$remote_addr, $forwarded_host, $forwarded_addr);
}

####################################################################
## ログ
sub logging {
    my ($msg)=@_;
    my @d = localtime();
    $msg = sprintf( "%d/%02d/%02d %02d:%02d:%02d %s (%s): %s\n",
		    $d[5]+1900, $d[4]+1, $d[3], $d[2], $d[1], $d[0],
		    $ENV{REMOTE_ADDR}, $0, $msg );
    ex_write_file ( "log/access_log", "log/access_log.lock", $msg );
}

####################################################################
## 排他的ファイル書き込み
sub ex_write_file {
    my ( $logfile, $lockfile, $message, $mode ) = @_;
    my $crit = 15; # LOCKFILE の存在が15秒続いてる時はきっと何かおかしい
    my $c = 0;
    while ( symlink ( $$, $lockfile )==0  ) {
	if ( ++$c > $crit ) {
	    unlink ( $lockfile ); # LOCKFILE を削除してループ脱出
	    symlink ( $$, $lockfile );
	    last;
	}
	Time::HiRes::sleep(0.1);
    }

    if ( $mode eq "replace" ) {
	open ( FD, ">$logfile" );
    } else {
	open ( FD, ">>$logfile" );
    }
    print FD ( $message );
    close ( FD );
    unlink ( $lockfile );
}

sub redirect_url {
    my $url=shift;
    print ( "Location: $url\n\n" );
    logging("Redirected to $url");
}

sub debug_str {
    my $str=shift;
    return if ($debug==0);
    printf("<p style=\"color: #00c\">%s</p>\n",escape_tag($str));
}

####################################################################
## 期限切れである旨を表示
sub print_expired {
    my $html = <<HTML
<p>このアンケートは終了しました。御協力ありがとうございました。</p>
</body>
</html>
HTML
    ;

    Jcode::convert(\$html,"utf-8");
    print $html;
}

####################################################################
## ログインパネル
sub show_login {
    my $msg=shift;

    my $html =  << "HTML"
$msg<form action="index.cgi" method="post">
<p>
広大ID/Hirodai ID: <br>
<input type="text" name="login_name" class="loginpanel"><br>
パスワード/Password: <br>
<input type="password" name="login_passwd" class="loginpanel"><br>
</p>
<input type="submit" value="ログイン/Login">
<input type="hidden" name="page" value="auth">
<input type="hidden" name="sid" value="$sid">
</form>
</body>
</html>
HTML
;

    Jcode::convert(\$html,"utf-8");
    print $html;
    
}

#

