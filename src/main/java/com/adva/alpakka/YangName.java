package com.adva.alpakka;

import javax.annotation.Nonnegative;
import javax.annotation.Nonnull;

import one.util.streamex.StreamEx;
import org.apache.commons.lang3.StringUtils;


public class YangName implements CharSequence {

    @Nonnull
    private final String name;

    public YangName(@Nonnull final String name) {
        this.name = name;
    }

    @Nonnull
    public String toPythonName() {
        return this.name.replace('-', '_');
    }

    @Nonnull
    public String toPythonClassName() {
        return StreamEx.of(this.name.split("-")).map(StringUtils::capitalize).joining();
    }

    @Nonnull @Override
    public String toString() {
        return this.name;
    }

    @Nonnegative @Override
    public int length() {
        return this.name.length();
    }

    @Override
    public char charAt(@Nonnegative final int index) {
        return this.name.charAt(index);
    }

    @Nonnull @Override
    public CharSequence subSequence(@Nonnegative final int start, @Nonnegative final int end) {
        return this.name.subSequence(start, end);
    }
}
