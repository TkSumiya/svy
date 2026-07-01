#! /usr/bin/perl
# $Id: auth.pl 446 2011-04-13 23:38:52Z sumi $

#use lib './pms';
use strict;
use Net::LDAP;
#use NKF;
use Encode 'encode';

%auth::auth_info;
my $ldap=1;
my $demouser=$ENV{SURVEY_ENABLE_DEMOUSER} ? 1 : 0; # 78999999  hogehoge 

#my $ldapurl = "ldaps://ldauthma.hiroshima-u.ac.jp";
my $ldapurl = "ldaps://uniauth.hiroshima-u.ac.jp";
#my $ldapurl = "ldaps://localhost";
my $ldapbase = "dc=hiroshima-u,dc=ac,dc=jp";
my $ldapbinddn = "uid=%s,ou=people,$ldapbase";

#my $ldapurl = "ldaps://ldap.riise.hiroshima-u.ac.jp";
#my $ldapbase = "dc=riise,dc=hiroshima-u,dc=ac,dc=jp";
#my $ldapbinddn = "uid=%s,ou=Users,$ldapbase";

my $ldapfilter = "(uid=%s)";

####################################################################
sub auth {
    my ($user, $pass)=@_;
    my ($k);

    $user = trim_space($user);
    
    return 0 if ( $user !~ /^[a-zA-Z0-9_-]+$/ );

#    foreach $k ( keys %pass ) {
#	return ( $pass eq $pass{$k} ) if ( $user eq $k );
#    }

    if ( $demouser == 1 ) {
	if ( $user eq "78999999" and $pass eq "hogehoge" ) {
	    logging( "demouser $user logged in" );
	    return 1;
	}
    }

    if ( $ldap ) {
	logging( "doing ldap authentication for $user" );
	return ldap_auth( $user, $pass );
    } elsif( $pass eq "hogehoge" ) {
	logging( "doing dumb authentication for $user" );
	return 1;
    }

    return 0;
}

sub ldap_auth {
    my ( $loginname, $passwd ) = @_;
    my ( $ldap, $mesg, $entry );

    logging("ldap->in");

    $ldap = Net::LDAP->new ( $ldapurl );
    if ( !$ldap ) {
	logging( "[Err] connection failed ($ldapurl)" );
	fatal_error ( $@ );
    }

    logging("ldap->new OK");

    $mesg = $ldap->bind (
			 sprintf($ldapbinddn,$loginname),
			 password => $passwd
			 );

    logging("ldap->bind OK");

#    $mesg = $ldap->bind; # anonymous binding

    if ( $mesg->code ) {
	return 0;
    }

    $mesg = $ldap->search ( 
#			    base => $ldapbase,
			    base => sprintf($ldapbinddn,$loginname),
			    filter => sprintf ( $ldapfilter, $loginname )
			    );

    logging("ldap->search OK");

    if ( $mesg->code ) {
	logging ( "[Err] ldapsearch failed ($loginname) err=" . $mesg->error );
	fatal_error ( $mesg->error );
    }

    if ( $mesg->count != 1 ) {
	logging ( "[Err] ldapsearch result is not unique ($loginname)? count=". $mesg->count );
	fatal_error ( "LDAP error, no uniq object found." );
    }

    $entry = $mesg->pop_entry;
    
    foreach ( sort $entry->attributes ) {
#	$auth::auth_info{$_} = nkf("-e -u",$entry->get_value($_));
	$auth::auth_info{$_} = encode("EUC-JP",$entry->get_value($_));
    }
 
    $mesg = $ldap->unbind;

    return 1;
}

sub trim_space {
    my $string = shift;
    $string =~ s/^\s*(.*?)\s*$/$1/;
    return ( $string );
}

1;
