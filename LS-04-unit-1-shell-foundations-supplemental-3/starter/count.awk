$2 == "ERROR" { errors++ }
$2 == "WARNING" { warnings++ }
END { printf "errors=%d warnings=%d\n", errors+0, warnings+0 }
